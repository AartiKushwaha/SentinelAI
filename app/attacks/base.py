from collections.abc import Iterator
from typing import Protocol

from app.attacks.registry import AttackScenario


class AttackModule(Protocol):
    def steps(self, scenario: AttackScenario) -> Iterator[str]: ...


class ConversationModule:
    """A scenario describes an ordered conversation against any capable adapter."""

    def steps(self, scenario: AttackScenario) -> Iterator[str]:
        yield from scenario.attack_steps
