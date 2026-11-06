from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_serializer, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import scenarios


class HttpProfile(BaseModel):
    """Operator-owned exact endpoint and credential pairing."""

    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=2048)
    method: Literal["POST", "PUT", "PATCH"] = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    auth_env: str | None = Field(None, pattern=r"^SENTINEL_CRED_[A-Z0-9_]+$")
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer "
    payload: dict = Field(default_factory=lambda: {"messages": "$messages"})
    text_path: str = "choices.0.message.content"
    decision_path: str | None = None
    usage_path: str | None = None
    trace_path: str | None = None
    requests_per_second: float = Field(2, gt=0, le=100)
    capabilities: set[Literal["chat", "rag", "tools", "agent"]] = {"chat"}
    # POST retries require a target that honors the supplied idempotency key.
    idempotent: bool = False

    @field_serializer("capabilities")
    def ordered_capabilities(self, values: set[str]) -> list[str]:
        return sorted(values)

    @model_validator(mode="after")
    def validate_headers(self):
        reserved = {
            "host",
            "content-length",
            "transfer-encoding",
            "connection",
            "accept-encoding",
            "idempotency-key",
        }
        if any(k.lower() in reserved for k in [*self.headers, self.auth_header]):
            raise ValueError("transport headers are managed by SentinelAI")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SENTINEL_", env_file=".env", extra="ignore")
    database_url: SecretStr = SecretStr("sqlite:///sentinel.db")
    scenario_dir: Path = Path(scenarios.__file__).parent
    profiles: dict[str, HttpProfile] = Field(default_factory=dict)
    timeout: float = Field(15, gt=0, le=120)
    concurrency: int = Field(4, ge=1, le=32)
    retries: int = Field(1, ge=0, le=3)
    creates_per_minute: int = Field(10, ge=1, le=120)
    max_active: int = Field(4, ge=1, le=16)
    max_bytes: int = Field(65536, ge=1024, le=1048576)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    provider: Literal["off", "hosted", "mock"] = "off"
    judge_profile: str | None = None
    judge_model: str | None = Field(None, max_length=200)
    min_confidence: float = Field(0.85, ge=0, le=1)
    price_per_million_tokens: float | None = Field(None, ge=0)
