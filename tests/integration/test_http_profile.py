from app.core.config import HttpProfile
from app.targets.base import Observation
from app.targets.mock import MockTarget


async def test_registration_consent_and_drift(service, monkeypatch):
    app, client = service
    jobs = app.state.jobs
    profile = HttpProfile(url="https://fixture.example/support")
    jobs.cfg.profiles["fixture"] = profile

    async def authorized_destination(url):
        return "https://8.8.8.8:443/support", "fixture.example", "fixture.example"

    monkeypatch.setattr("app.api.routes.pin_destination", authorized_destination)
    target = (
        await client.post(
            "/api/v1/targets",
            json={"name": "fixture", "adapter": "http", "authorized": True, "profile": "fixture"},
        )
    ).json()
    assert "url" not in target["configuration"]
    jobs.http["fixture"] = MockTarget([Observation(text="Ambiguous")])
    request = {"target_id": target["id"], "scenario_ids": ["data_leakage-direct"]}
    result = await client.post("/api/v1/assessments", json=request)
    assert result.status_code == 202
    import asyncio

    await asyncio.gather(*jobs.jobs.values())
    report = (await client.get("/api/v1/assessments/" + result.json()["id"] + "/report")).json()
    assert report["metrics"]["inconclusive"] == 1
    assert (
        await client.post("/api/v1/assessments", json={**request, "scenario_ids": ["rag-tenant"]})
    ).status_code == 422
    jobs.cfg.profiles["fixture"] = profile.model_copy(
        update={"url": "https://changed.example/support"}
    )
    assert (await client.post("/api/v1/assessments", json=request)).status_code == 409
