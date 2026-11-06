from app.attacks.registry import Registry
from app.core.config import Settings
from app.evaluation.rules import evaluate
from app.targets.base import Observation, ToolEvent


def test_permitted_receipt_does_not_prove_tool_abuse():
    cases = Registry(Settings().scenario_dir).entries
    for case, tool, arg, approved in [
        ("tool_misuse-approval", "ticket", "support", True),
        ("tool_misuse-scopes", "account", "north", False),
    ]:
        obs = Observation(
            text="operation completed",
            tools=[
                ToolEvent(
                    tool=tool,
                    actor="support",
                    tenant="north",
                    arguments={"value": arg},
                    approved=approved,
                    status="executed",
                )
            ],
        )
        assert evaluate(cases[case], [obs]).outcome == "INCONCLUSIVE"


def test_mention_without_disclosure():
    s = Registry(Settings().scenario_dir).entries["data_leakage-direct"]
    result = evaluate(s, [Observation(text="An API key is a credential.")])
    assert result.outcome == "INCONCLUSIVE" and "mentioned" in result.explanation
