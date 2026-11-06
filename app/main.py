from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.guard import RequestGuard
from app.api.routes import routes
from app.api.schemas import Problem
from app.attacks.registry import Registry
from app.core.config import Settings
from app.core.logging import configure
from app.database.models import Report
from app.database.store import Store
from app.orchestration.engine import Scheduler


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()
    store = Store(cfg.database_url.get_secret_value())
    configure(cfg.log_level)
    registry = Registry(cfg.scenario_dir)
    jobs = Scheduler(cfg, store, registry)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        jobs.recover()
        try:
            yield
        finally:
            await jobs.close()
            store.engine.dispose()

    api = FastAPI(
        title="SentinelAI",
        version="0.1.0",
        lifespan=lifespan,
        description="Single-operator, evidence-driven assessments of explicitly authorized AI applications.",
    )
    api.state.store = store
    api.state.jobs = jobs
    api.add_middleware(RequestGuard, limit=cfg.max_bytes)
    api.include_router(routes(cfg, store, registry, jobs))

    @api.exception_handler(Problem)
    async def problem_handler(_: Request, exc: Problem):
        return JSONResponse({"error": {"code": exc.code}}, exc.status)

    @api.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError):
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_request",
                    "fields": [{"location": e["loc"], "type": e["type"]} for e in exc.errors()],
                }
            },
            422,
        )

    @api.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        return JSONResponse({"error": {"code": f"http_{exc.status_code}"}}, exc.status_code)

    @api.exception_handler(SQLAlchemyError)
    async def db_error(_: Request, exc: SQLAlchemyError):
        return JSONResponse({"error": {"code": "database_unavailable"}}, 503)

    @api.get("/health")
    async def health():
        return {"status": "alive"}

    @api.get("/ready")
    def ready():
        try:
            with store.session() as session:
                session.execute(select(Report.id).limit(1))
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ready"}

    return api


app = create_app()
