from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.attacks.registry import Category, Severity


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TargetRegistration(Input):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.-]*$")
    adapter: Literal["demo", "http"] = "demo"
    kind: Literal["llm", "rag", "agent", "tool_agent", "mcp_agent"] = "llm"
    mode: Literal["secured", "vulnerable"] = "secured"
    forbidden_actions: set[Literal["publish"]] = {"publish"}
    profile: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    authorized: bool = False

    @model_validator(mode="after")
    def remote_consent(self) -> Self:
        if self.adapter == "http" and (not self.profile or not self.authorized):
            raise ValueError("HTTP registration requires an authorized profile")
        if self.adapter == "demo" and self.profile:
            raise ValueError("demo runs in process")
        return self


class StartAssessment(Input):
    target_id: UUID
    scenario_ids: list[str] | None = Field(default=None, min_length=1, max_length=256)
    category: Category | None = None
    severity: Severity | None = None
    concurrency: int | None = Field(default=None, ge=1, le=32)


class Review(Input):
    status: Literal["reviewed", "dismissed", "confirmed"]


class TargetView(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    configuration: dict


class RunState(BaseModel):
    id: UUID
    status: Literal["queued", "running", "cancelled", "completed", "interrupted"]


class RunSummary(RunState):
    target_id: UUID
    created_at: datetime
    duration_seconds: float


class RunDetail(RunSummary):
    configuration: dict
    scenarios: list[dict]
    metrics: dict


class ErrorBody(BaseModel):
    code: str
    fields: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Problem(Exception):
    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code
