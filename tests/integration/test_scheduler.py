import asyncio

from app.demo.lab import SecurityLab
from app.targets.base import Observation, TargetError
from tests.conftest import start_and_wait


async def test_concurrency_failure_isolation_and_timeout(service, monkeypatch):
    app, client = service
    jobs = app.state.jobs
    jobs.cfg.timeout = 0.06
    active = peak = 0

    async def controlled(self, request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            text = request.messages[-1].content
            if "API" in text or "test key" in text:
                raise TargetError("fixture_failed")
            if "forecast" in text:
                await asyncio.sleep(0.2)
            else:
                await asyncio.sleep(0.005)
            return Observation(text="ambiguous")
        finally:
            active -= 1

    monkeypatch.setattr(SecurityLab, "send", controlled)
    _, run = await start_and_wait(client, category="data_leakage", concurrency=2)
    metrics = run["metrics"]
    assert peak == 2 and metrics["errors"] == 2 and metrics["inconclusive"] == 4
    assert metrics["asr"] is None


async def test_sequential_and_advisory_review(service, monkeypatch):
    from app.evaluation.judge import MockJudge

    app, client = service
    app.state.jobs.judge = MockJudge()

    async def ambiguous(self, request):
        return Observation(text="I cannot tell.")

    monkeypatch.setattr(SecurityLab, "send", ambiguous)
    path, _ = await start_and_wait(client, concurrency=1, scenario_ids=["data_leakage-direct"])
    result = (await client.get(path + "/report")).json()["executions"][0]
    assert result["outcome"] == "INCONCLUSIVE"
    assert result["review_status"] == "pending" and result["advisor"]["review_required"]
