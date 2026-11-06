import asyncio
import json

import pytest

from app.attacks.registry import Registry
from app.core.config import Settings
from app.demo.data import PRIVATE
from app.evaluation.evidence import project
from app.evaluation.rules import evaluate
from app.targets.base import Observation, ToolEvent


async def test_remote_authorization_and_browser_boundary(service):
    _, client = service
    path = "/api/v1/targets"
    for payload in [
        {"adapter": "http", "profile": "a"},
        {"adapter": "http", "profile": "missing", "authorized": True},
        {"url": "https://8.8.8.8"},
    ]:
        assert (await client.post(path, json={"name": "test", **payload})).status_code == 422
    assert (
        await client.post(path, json={"name": "test"}, headers={"origin": "https://other.example"})
    ).status_code == 403
    assert (await client.get(path, headers={"host": "attacker.example"})).status_code == 400
    assert (await client.post(path, content=b"x" * 66000)).status_code == 413
    res = await client.post(path, json={"name": PRIVATE["token"], "api_key": PRIVATE["token"]})
    assert PRIVATE["token"] not in res.text


def test_projection_drops_arbitrary_values():
    scenario = next(iter(Registry(Settings().scenario_dir).entries.values()))
    raw = "unknown-sensitive-value"
    obs = Observation(
        text=raw + PRIVATE["token"],
        documents=[raw],
        tools=[ToolEvent(tool=raw, actor=raw, tenant=raw, arguments={raw: raw}, status="executed")],
    )
    evidence = json.dumps(project(scenario, [obs]))
    assert raw not in evidence and PRIVATE["token"] not in evidence
    assert "matched_synthetic_fields" in evidence


async def test_rate_limit_and_cancel(service, monkeypatch):
    app, client = service
    jobs = app.state.jobs
    jobs.cfg.creates_per_minute = 1
    from app.demo.lab import SecurityLab

    async def slow(self, request):
        await asyncio.sleep(10)

    monkeypatch.setattr(SecurityLab, "send", slow)
    target = (await client.post("/api/v1/targets", json={"name": "slow"})).json()
    body = {"target_id": target["id"], "concurrency": 1}
    run = (await client.post("/api/v1/assessments", json=body)).json()
    await asyncio.sleep(0.01)
    path = "/api/v1/assessments/" + run["id"]
    assert (await client.get(path + "/report")).status_code == 409
    assert (await client.post("/api/v1/assessments", json=body)).status_code == 429
    assert (await client.post(path + "/cancel")).status_code == 200
    await asyncio.sleep(0.01)
    report = (await client.get(path + "/report")).json()
    assert report["status"] == "cancelled" and report["metrics"]["executed"] == 0
    assert {c["status"] for c in report["coverage"]} == {"cancelled"}


@pytest.mark.parametrize("cat", ["tool_misuse", "rag"])
def test_denial_without_required_trace(cat):
    scenario = next(
        s
        for s in Registry(Settings().scenario_dir).entries.values()
        if s.category == cat and s.evaluation_rules[0].kind.startswith("forbidden_")
    )
    assert (
        evaluate(scenario, [Observation(text="denied", decision="denied")]).outcome
        == "INCONCLUSIVE"
    )
