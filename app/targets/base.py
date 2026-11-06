from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Interaction(BaseModel):
    messages: list[Message]
    request_id: str


class ToolEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str = Field(max_length=64)
    actor: str = Field(max_length=64)
    user: str | None = Field(default=None, max_length=64)
    tenant: str = Field(max_length=64)
    arguments: dict[str, str]
    status: Literal["executed", "denied"]
    approved: bool = False


class Observation(BaseModel):
    text: str = Field(max_length=100000)
    decision: Literal["answered", "denied"] | None = None
    documents: list[str] = Field(default_factory=list, max_length=128)
    tools: list[ToolEvent] = Field(default_factory=list, max_length=128)
    tokens: int | None = Field(None, ge=0, le=100_000_000)


class TargetAdapter(Protocol):
    async def send(self, request: Interaction) -> Observation: ...


class TargetError(Exception):
    """Safe, bounded error code for a failed interaction."""


class TransientError(TargetError):
    """A transient transport failure, retryable only for idempotent targets."""
