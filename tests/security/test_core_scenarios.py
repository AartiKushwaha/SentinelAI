import pytest

from app.attacks.base import ConversationModule
from app.attacks.registry import Registry
from app.core.config import Settings
from app.evaluation.rules import evaluate
from app.orchestration.execution import execute
from app.targets.base import Observation, TransientError
from app.targets.demo import DemoTarget
from app.targets.mock import MockTarget

cases = [
    s
    for s in Registry(Settings().scenario_dir).entries.values()
    if s.category.value in {"data_leakage", "jailbreak", "prompt_injection"}
    and s.target_requirements == {"chat"}
]


@pytest.mark.parametrize("scenario", cases, ids=lambda s: s.id)
@pytest.mark.parametrize("secured", [True, False])
async def test_core_scenario(scenario, secured):
    trial = await execute(scenario, ConversationModule(), DemoTarget(secured), "case", 1, 0)
    assert trial.result.outcome == ("PASS" if secured else "FAIL")


def test_keyword_and_echo_do_not_prove_violation():
    scenario = next(s for s in cases if s.id == "prompt_injection-direct")
    for text in ["There is an API key.", scenario.attack_steps[0], "I refuse."]:
        assert evaluate(scenario, [Observation(text=text)]).outcome == "INCONCLUSIVE"


async def test_transient_retry_preserves_key():
    target = MockTarget([TransientError("busy"), Observation(text="Denied", decision="denied")])
    trial = await execute(cases[0], ConversationModule(), target, "case", 1, 1)
    assert trial.attempts == 2 and trial.result.outcome == "PASS"
    assert target.requests[0].request_id == target.requests[1].request_id
