import hashlib

import pytest
from sqlalchemy import func, select

from app.database.models import Audit, Report
from app.demo.data import PRIVATE
from tests.conftest import start_and_wait


@pytest.mark.parametrize("mode", ["vulnerable", "secured"])
async def test_full_assessment(service, mode):
    app, client = service
    assert (await client.get("/ready")).status_code == 200
    assert "/api/v1/targets" in (await client.get("/openapi.json")).json()["paths"]
    assert len((await client.get("/api/v1/scenarios?category=rag&limit=2")).json()) == 2
    path, run = await start_and_wait(client, mode)
    count = len((await client.get("/api/v1/scenarios?limit=100")).json())
    assert run["metrics"]["executed"] == count
    expected = count if mode == "vulnerable" else 0
    assert run["metrics"]["failed"] == expected
    assert run["metrics"]["passed"] == count - expected
    assert run["metrics"]["asr"] == expected / count
    findings = (await client.get(path + "/findings")).json()
    assert len(findings) == expected
    for fmt in ("json", "html", "markdown"):
        response = await client.get(path + "/report", params={"format": fmt})
        assert response.status_code == 200
        assert not any(secret in response.text for secret in PRIVATE.values())
        assert (
            response.content == (await client.get(path + "/report", params={"format": fmt})).content
        )
        assert response.headers["etag"] == '"' + hashlib.sha256(response.content).hexdigest() + '"'
    report = (await client.get(path + "/report")).json()
    with app.state.store.session() as db:
        assert db.scalar(select(func.count()).select_from(Audit)) > 0
        assert (
            len(
                db.scalars(
                    select(Report).where(Report.assessment_id == __import__("uuid").UUID(run["id"]))
                ).all()
            )
            == 3
        )
    eid = report["executions"][0]["execution_id"]
    review = await client.patch(
        path + "/executions/" + eid + "/review", json={"status": "reviewed"}
    )
    assert review.status_code == 200
    assert (await client.get(path + "/report")).json()["executions"][0][
        "review_status"
    ] == "reviewed"
    assert (await client.delete("/api/v1/targets/" + run["target_id"])).status_code == 409


async def test_target_lifecycle(service):
    _, client = service
    target = (await client.post("/api/v1/targets", json={"name": "temporary"})).json()
    path = "/api/v1/targets/" + target["id"]
    assert (await client.get(path)).json()["configuration"]["mode"] == "secured"
    assert (
        await client.post(
            "/api/v1/assessments", json={"target_id": target["id"], "scenario_ids": ["unknown"]}
        )
    ).status_code == 422
    assert (await client.delete(path)).status_code == 204
    assert (await client.get(path)).status_code == 404
