from uuid import UUID

from sqlalchemy import select

from app.database.models import Assessment, Selection
from tests.conftest import start_and_wait


async def test_recovery_finalizes_orphaned_selection(service):
    app, client = service
    path, run = await start_and_wait(client, scenario_ids=["rag-tenant"])
    with app.state.store.session.begin() as db:
        original = db.get(Assessment, UUID(run["id"]))
        interrupted = Assessment(
            target_id=original.target_id, config=original.config, status="running"
        )
        db.add(interrupted)
        db.flush()
        selected = db.scalar(select(Selection).where(Selection.assessment_id == original.id))
        db.add(
            Selection(
                assessment_id=interrupted.id,
                definition_id=selected.definition_id,
                position=0,
                status="running",
            )
        )
    app.state.jobs.recover()
    report = (await client.get("/api/v1/assessments/" + str(interrupted.id) + "/report")).json()
    assert report["status"] == "interrupted" and report["coverage"][0]["status"] == "interrupted"
    assert report["metrics"]["executed"] == 0 and report["metrics"]["asr"] is None
