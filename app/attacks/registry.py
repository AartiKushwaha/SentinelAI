import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.demo.data import PRIVATE


class Category(StrEnum):
    injection = "prompt_injection"
    jailbreak = "jailbreak"
    leakage = "data_leakage"
    rag = "rag"
    tools = "tool_misuse"
    privilege = "privilege_escalation"


Severity = Literal["Critical", "High", "Medium", "Low", "Informational"]
Short = Annotated[str, Field(min_length=1, max_length=512)]


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["exact_output", "seeded_secret", "forbidden_document", "forbidden_tool"]
    value: Short
    safe_output: Short | None = None
    arguments: dict[str, Short] = Field(default_factory=dict, max_length=12)
    actor: Short | None = None
    approved: bool | None = None

    @model_validator(mode="after")
    def validate_fixture(self):
        if self.kind == "seeded_secret" and self.value not in PRIVATE:
            raise ValueError("unknown synthetic fixture")
        if self.kind != "forbidden_tool" and (
            self.arguments or self.actor or self.approved is not None
        ):
            raise ValueError("dispatch predicates require a tool rule")
        return self


class AttackScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    name: Short
    category: Category
    description: Short
    severity: Severity
    enabled: bool = True
    tags: list[Short] = Field(default_factory=list, max_length=12)
    target_requirements: set[Literal["chat", "rag", "tools", "agent"]] = Field(min_length=1)
    setup: Short
    attack_steps: list[Annotated[str, Field(min_length=1, max_length=4096)]] = Field(
        min_length=1, max_length=8
    )
    expected_secure_behaviour: Short
    expected_vulnerable_behaviour: Short
    evaluation_rules: list[Rule] = Field(min_length=1, max_length=8)
    impact: Short
    remediation: Short
    references: list[Short] = Field(min_length=1, max_length=8)


class Registry:
    def __init__(self, directory: Path):
        self.entries: dict[str, AttackScenario] = {}
        for path in sorted(directory.glob("*.json")):
            if path.stat().st_size > 1048576:
                raise ValueError(f"oversize scenario file: {path.name}")
            scenarios = TypeAdapter(list[AttackScenario]).validate_python(
                json.loads(path.read_bytes())
            )
            for scenario in scenarios:
                if scenario.id in self.entries:
                    raise ValueError(f"duplicate scenario ID: {scenario.id}")
                self.entries[scenario.id] = scenario
        if not self.entries or len(self.entries) > 1000:
            raise ValueError("registry must contain 1 to 1000 scenarios")
