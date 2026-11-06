import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATA = JSON().with_variant(JSONB(), "postgresql")


def now() -> datetime:
    # Both dialects store a UTC timestamp without local-time conversion.
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Entity(Base):
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(default=now, index=True)


class Target(Entity):
    __tablename__ = "targets"
    name: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(DATA)


class Assessment(Entity):
    __tablename__ = "assessments"
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True, default="queued")
    config: Mapped[dict] = mapped_column(DATA)
    duration: Mapped[float] = mapped_column(default=0.0)


class Definition(Entity):
    __tablename__ = "definitions"
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    scenario_id: Mapped[str] = mapped_column(String(80), index=True)
    body: Mapped[dict] = mapped_column(DATA)


class Selection(Entity):
    __tablename__ = "assessment_scenarios"
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), index=True)
    definition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("definitions.id"))
    position: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="pending")
    __table_args__ = (UniqueConstraint("assessment_id", "position"),)


class AttackExecution(Entity):
    __tablename__ = "executions"
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_scenarios.id"), unique=True
    )
    evidence: Mapped[dict] = mapped_column(DATA)
    latency: Mapped[float]
    tokens: Mapped[int | None]
    attempts: Mapped[int]


class Evaluation(Entity):
    __tablename__ = "evaluations"
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), unique=True)
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    details: Mapped[dict] = mapped_column(DATA)
    review_status: Mapped[str] = mapped_column(String(20))


class Finding(Entity):
    __tablename__ = "findings"
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), unique=True)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    details: Mapped[dict] = mapped_column(DATA)


class Audit(Entity):
    __tablename__ = "tool_audits"
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    details: Mapped[dict] = mapped_column(DATA)


class Report(Entity):
    __tablename__ = "reports"
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"))
    format: Mapped[str] = mapped_column(String(12))
    digest: Mapped[str] = mapped_column(String(64))
    __table_args__ = (Index("ix_report_assessment_format", "assessment_id", "format", unique=True),)
