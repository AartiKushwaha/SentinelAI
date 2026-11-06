import asyncio
import hashlib
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.schemas import (
    ErrorResponse,
    Problem,
    Review,
    RunDetail,
    RunState,
    RunSummary,
    StartAssessment,
    TargetRegistration,
    TargetView,
)
from app.attacks.registry import AttackScenario, Category, Registry, Severity
from app.core.config import Settings
from app.core.security import digest, pin_destination
from app.database.models import Assessment, AttackExecution, Evaluation, Report, Selection, Target
from app.database.store import Store
from app.orchestration.engine import ACTIVE, Scheduler
from app.reporting.formats import render
from app.reporting.reports import snapshot
from app.targets.base import TargetError

Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


def routes(settings: Settings, store: Store, registry: Registry, jobs: Scheduler) -> APIRouter:
    api = APIRouter(
        prefix="/api/v1",
        responses={
            code: {"model": ErrorResponse} for code in (400, 403, 404, 409, 413, 422, 429, 503)
        },
    )

    def target_view(t: Target) -> dict:
        return {
            "id": str(t.id),
            "name": t.name,
            "created_at": t.created_at,
            "configuration": t.config,
        }

    def run_view(run: Assessment) -> dict:
        return {
            "id": str(run.id),
            "target_id": str(run.target_id),
            "created_at": run.created_at,
            "status": run.status,
            "duration_seconds": run.duration,
        }

    @api.post("/targets", status_code=201, response_model=TargetView)
    async def register(body: TargetRegistration):
        if settings.public_demo:
            raise Problem(403, "demo_targets_are_preconfigured")
        config = body.model_dump(mode="json", exclude={"name"})
        if body.adapter == "http":
            if body.profile == settings.judge_profile or body.profile not in settings.profiles:
                raise Problem(422, "unknown_target_profile")
            profile = settings.profiles[str(body.profile)]
            try:
                async with asyncio.timeout(settings.timeout):
                    await pin_destination(profile.url)
            except (TargetError, TimeoutError) as error:
                raise Problem(422, "target_destination_rejected") from error
            config["profile_digest"] = digest(profile.model_dump(mode="json"))
        with store.session.begin() as db:
            target = Target(name=body.name, config=config)
            db.add(target)
            db.flush()
            return target_view(target)

    @api.get("/targets", response_model=list[TargetView])
    async def targets(offset: Offset = 0, limit: Limit = 50):
        with store.session() as db:
            return [
                target_view(t)
                for t in db.scalars(
                    select(Target)
                    .order_by(Target.created_at, Target.id)
                    .offset(offset)
                    .limit(limit)
                )
            ]

    @api.get("/targets/{target_id}", response_model=TargetView)
    async def get_target(target_id: UUID):
        with store.session() as db:
            target = db.get(Target, target_id)
            if not target:
                raise Problem(404, "target_not_found")
            return target_view(target)

    @api.delete("/targets/{target_id}", status_code=204)
    async def delete_target(target_id: UUID):
        if settings.public_demo:
            raise Problem(403, "demo_targets_are_preconfigured")
        try:
            with store.session.begin() as db:
                target = db.get(Target, target_id)
                if not target:
                    raise Problem(404, "target_not_found")
                db.delete(target)
        except IntegrityError as error:
            raise Problem(409, "target_has_assessments") from error
        return Response(status_code=204)

    @api.get("/scenarios", response_model=list[AttackScenario])
    async def scenarios(
        offset: Offset = 0,
        limit: Limit = 50,
        category: Category | None = None,
        severity: Severity | None = None,
        enabled: bool | None = None,
    ):
        return [
            s
            for s in registry.entries.values()
            if (not category or s.category == category)
            and (not severity or s.severity == severity)
            and (enabled is None or s.enabled == enabled)
        ][offset : offset + limit]

    @api.get("/scenarios/{scenario_id}", response_model=AttackScenario)
    async def scenario(scenario_id: str):
        if scenario_id not in registry.entries:
            raise Problem(404, "scenario_not_found")
        return registry.entries[scenario_id]

    @api.post("/assessments", status_code=202, response_model=RunState)
    async def start(body: StartAssessment):
        return {"id": jobs.submit(body), "status": "queued"}

    @api.get("/assessments", response_model=list[RunSummary])
    async def assessments(
        offset: Offset = 0,
        limit: Limit = 50,
        status: str | None = None,
        target_id: UUID | None = None,
    ):
        stmt = select(Assessment).order_by(Assessment.created_at.desc(), Assessment.id)
        if status:
            stmt = stmt.where(Assessment.status == status)
        if target_id:
            stmt = stmt.where(Assessment.target_id == target_id)
        with store.session() as db:
            return [run_view(r) for r in db.scalars(stmt.offset(offset).limit(limit))]

    @api.get("/assessments/{run_id}", response_model=RunDetail)
    async def assessment(run_id: UUID):
        with store.session() as db:
            run = db.get(Assessment, run_id)
            if not run:
                raise Problem(404, "assessment_not_found")
            doc = snapshot(db, run)
            return {
                **run_view(run),
                "configuration": run.config,
                "scenarios": doc["coverage"],
                "metrics": doc["metrics"],
            }

    @api.post("/assessments/{run_id}/cancel", response_model=RunState)
    async def cancel(run_id: UUID):
        with store.session() as db:
            run = db.get(Assessment, run_id)
            if not run:
                raise Problem(404, "assessment_not_found")
            if run.status not in ACTIVE and run.status != "cancelled":
                raise Problem(409, "assessment_terminal")
        await jobs.stop(run_id)
        return {"id": run_id, "status": "cancelled"}

    @api.get("/assessments/{run_id}/findings")
    async def findings(
        run_id: UUID,
        offset: Offset = 0,
        limit: Limit = 50,
        severity: Severity | None = None,
        category: Category | None = None,
    ):
        with store.session() as db:
            run = db.get(Assessment, run_id)
            if not run:
                raise Problem(404, "assessment_not_found")
            return [
                f
                for f in snapshot(db, run)["findings"]
                if (not severity or f["severity"] == severity)
                and (not category or f["category"] == category)
            ][offset : offset + limit]

    @api.patch("/assessments/{run_id}/executions/{execution_id}/review")
    async def review(run_id: UUID, execution_id: UUID, body: Review):
        if settings.public_demo:
            raise Problem(403, "review_requires_operator_deployment")
        with store.session.begin() as db:
            evaluation = db.scalar(
                select(Evaluation)
                .join(AttackExecution)
                .join(Selection)
                .where(Selection.assessment_id == run_id, AttackExecution.id == execution_id)
            )
            if not evaluation:
                raise Problem(404, "execution_not_found")
            evaluation.review_status = body.status
            return {"review_status": body.status, "outcome": evaluation.outcome}

    @api.get("/assessments/{run_id}/report")
    async def report(run_id: UUID, format: Literal["json", "html", "markdown"] = "json"):
        with store.session.begin() as db:
            run = db.get(Assessment, run_id)
            if not run:
                raise Problem(404, "assessment_not_found")
            if run.status in ACTIVE:
                raise Problem(409, "assessment_active")
            body = render(snapshot(db, run), format)
            signature = hashlib.sha256(body.encode()).hexdigest()
            record = db.scalar(
                select(Report).where(Report.assessment_id == run_id, Report.format == format)
            )
            if not record:
                db.add(Report(assessment_id=run_id, format=format, digest=signature))
            else:
                record.digest = signature
            return Response(
                body,
                media_type={
                    "json": "application/json",
                    "html": "text/html",
                    "markdown": "text/markdown",
                }[format],
                headers={
                    "ETag": f'"{signature}"',
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
                },
            )

    @api.get("/metrics/summary")
    async def summary():
        with store.session() as db:
            counts = {
                outcome: count
                for outcome, count in db.execute(
                    select(Evaluation.outcome, func.count()).group_by(Evaluation.outcome)
                )
            }
            decided = counts.get("PASS", 0) + counts.get("FAIL", 0)
            return {
                "assessments": db.scalar(select(func.count()).select_from(Assessment)),
                "executed": sum(counts.values()),
                "outcomes": counts,
                "decided": decided,
                "asr": counts.get("FAIL", 0) / decided if decided else None,
            }

    return api
