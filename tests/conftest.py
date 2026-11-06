import asyncio
import os

import httpx
import pytest
from alembic.config import Config
from pydantic import SecretStr

from alembic import command
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
async def service(tmp_path, monkeypatch):
    url = os.environ.get("SENTINEL_TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("SENTINEL_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    cfg = Settings(
        _env_file=None,
        database_url=SecretStr(url),
        profiles={},
        provider="off",
        creates_per_minute=30,
    )
    app = create_app(cfg)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            yield app, client


async def start_and_wait(client, mode="vulnerable", **options):
    target = (await client.post("/api/v1/targets", json={"name": "fixture", "mode": mode})).json()
    resp = await client.post("/api/v1/assessments", json={"target_id": target["id"], **options})
    assert resp.status_code == 202, resp.text
    path = "/api/v1/assessments/" + resp.json()["id"]
    async with asyncio.timeout(30):
        while True:
            result = (await client.get(path)).json()
            if result["status"] not in {"queued", "running"}:
                break
            await asyncio.sleep(0.01)
    assert result["status"] == "completed", result
    return path, result
