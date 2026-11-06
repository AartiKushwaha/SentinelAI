import asyncio

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import HttpProfile, Settings
from app.database.models import Assessment, AttackExecution, Audit, Evaluation, Finding, Report
from app.database.retention import trim_demo_history
from dashboard.runtime import DemoRuntime
from tests.conftest import start_and_wait


def test_public_demo_startup_and_boundaries():
    runtime = DemoRuntime()
    try:
        with httpx.Client(base_url=runtime.base_url, trust_env=False) as client:
            summary = client.get("/api/v1/metrics/summary").raise_for_status().json()
            assert summary["outcomes"] == {"FAIL": 41, "PASS": 41}
            targets = client.get("/api/v1/targets").raise_for_status().json()
            assert len(targets) == 2
            assert client.post("/api/v1/targets", json={"name": "visitor"}).status_code == 403
            assert client.delete("/api/v1/targets/" + targets[0]["id"]).status_code == 403
            history = client.get("/api/v1/assessments").raise_for_status().json()
            report = client.get("/api/v1/assessments/" + history[0]["id"] + "/report")
            assert report.status_code == 200
            assert client.get("/ready", headers={"host": "external.example"}).status_code == 400
    finally:
        runtime.close()
    assert not runtime.thread.is_alive()


def test_public_demo_rejects_network_profiles():
    with pytest.raises(ValidationError, match="offline"):
        Settings(public_demo=True, provider="mock")
    with pytest.raises(ValidationError, match="local"):
        Settings(public_demo=True, profiles={"remote": HttpProfile(url="https://example.com")})


async def test_retention_cleans_related_rows_and_preserves_recent_history(service):
    app, client = service
    first, _ = await start_and_wait(client, scenario_ids=["tool_misuse-approval"])
    await client.get(first + "/report")
    second, _ = await start_and_wait(client, scenario_ids=["data_leakage-direct"])
    await asyncio.sleep(0)
    with app.state.store.session.begin() as db:
        trim_demo_history(db, limit=2)
        assert db.scalar(select(func.count()).select_from(Assessment)) == 1
        assert db.scalar(select(func.count()).select_from(AttackExecution)) == 1
        assert db.scalar(select(func.count()).select_from(Evaluation)) == 1
        assert db.scalar(select(func.count()).select_from(Finding)) == 1
        assert db.scalar(select(func.count()).select_from(Audit)) == 0
        assert db.scalar(select(func.count()).select_from(Report)) == 0
    assert (await client.get(first)).status_code == 404
    assert (await client.get(second)).status_code == 200
