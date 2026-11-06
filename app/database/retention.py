"""Bound storage for the shared synthetic demonstration."""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.schemas import Problem
from app.database.models import (
    Assessment,
    AttackExecution,
    Audit,
    Evaluation,
    Finding,
    Report,
    Selection,
)


def trim_demo_history(db: Session, limit: int = 50) -> None:
    """Reserve one run slot, deleting only terminal demo runs in this transaction."""
    count = db.scalar(select(func.count()).select_from(Assessment)) or 0
    excess = count - limit + 1
    if excess <= 0:
        return
    expired = list(
        db.scalars(
            select(Assessment.id)
            .where(Assessment.status.in_(("completed", "cancelled", "interrupted")))
            .order_by(Assessment.created_at, Assessment.id)
            .limit(excess)
        )
    )
    if len(expired) < excess:
        raise Problem(429, "demo_history_capacity")
    selections = select(Selection.id).where(Selection.assessment_id.in_(expired))
    executions = select(AttackExecution.id).where(AttackExecution.selection_id.in_(selections))
    db.execute(delete(Audit).where(Audit.execution_id.in_(executions)))
    db.execute(delete(Finding).where(Finding.assessment_id.in_(expired)))
    db.execute(delete(Evaluation).where(Evaluation.execution_id.in_(executions)))
    db.execute(delete(AttackExecution).where(AttackExecution.selection_id.in_(selections)))
    db.execute(delete(Selection).where(Selection.assessment_id.in_(expired)))
    db.execute(delete(Report).where(Report.assessment_id.in_(expired)))
    db.execute(delete(Assessment).where(Assessment.id.in_(expired)))
