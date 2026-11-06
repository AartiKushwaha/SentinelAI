"""Own the local-only API lifecycle inside a hosted Streamlit process."""

import atexit
import socket
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from alembic.config import Config
from pydantic import SecretStr

from alembic import command
from app.api.schemas import TargetRegistration
from app.core.config import Settings
from app.database.models import Target
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


class DemoRuntime:
    def __init__(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="sentinel-public-")
        database_url = "sqlite:///" + (Path(self.directory.name) / "demo.db").as_posix()
        migration = Config(str(ROOT / "alembic.ini"))
        migration.attributes["database_url"] = database_url
        command.upgrade(migration, "head")
        settings = Settings(
            _env_file=None,
            database_url=SecretStr(database_url),
            scenario_dir=ROOT / "scenarios",
            profiles={},
            provider="off",
            judge_profile=None,
            judge_model=None,
            public_demo=True,
            concurrency=2,
            max_active=2,
            creates_per_minute=6,
            timeout=10,
            retries=0,
            min_confidence=0.85,
            price_per_million_tokens=None,
        )
        self.api = create_app(settings)
        target_ids = []
        with self.api.state.store.session.begin() as db:
            for mode in ("vulnerable", "secured"):
                registration = TargetRegistration(
                    name=f"Support lab {mode}", kind="mcp_agent", mode=mode
                )
                target = Target(
                    name=registration.name,
                    config=registration.model_dump(mode="json", exclude={"name"}),
                )
                db.add(target)
                db.flush()
                target_ids.append(str(target.id))
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.base_url = f"http://127.0.0.1:{self.listener.getsockname()[1]}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                self.api,
                host="127.0.0.1",
                access_log=False,
                log_level="warning",
                timeout_graceful_shutdown=5,
            )
        )
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.listener]},
            daemon=True,
            name="sentinel-demo-api",
        )
        self.thread.start()
        atexit.register(self.close)
        try:
            self._wait_ready()
            with httpx.Client(base_url=self.base_url, trust_env=False, timeout=15) as client:
                runs = [
                    client.post("/api/v1/assessments", json={"target_id": target_id})
                    .raise_for_status()
                    .json()["id"]
                    for target_id in target_ids
                ]
                deadline = time.monotonic() + 45
                for run in runs:
                    while True:
                        state = client.get(f"/api/v1/assessments/{run}").raise_for_status().json()
                        if state["status"] == "completed":
                            break
                        if (
                            state["status"] not in {"queued", "running"}
                            or time.monotonic() > deadline
                        ):
                            raise RuntimeError("Demo initialization did not finish")
                        time.sleep(0.1)
        except Exception:
            self.close()
            raise

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + 30
        while self.thread.is_alive() and time.monotonic() < deadline:
            try:
                response = httpx.get(self.base_url + "/ready", trust_env=False, timeout=1)
                if response.status_code == 200:
                    return
            except httpx.TransportError:
                # Connection refusal is expected before Uvicorn binds the prepared socket.
                pass
            time.sleep(0.1)
        raise RuntimeError("The local demonstration API did not become ready")

    def close(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=8)
        if not self.thread.is_alive():
            self.listener.close()
            self.api.state.store.engine.dispose()
            self.directory.cleanup()
        atexit.unregister(self.close)
