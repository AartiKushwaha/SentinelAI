from app.attacks.registry import AttackScenario
from app.demo.data import PRIVATE
from app.demo.retrieval import CORPUS
from app.evaluation.rules import violates
from app.targets.base import Observation, ToolEvent


def project_tool(event: ToolEvent) -> dict:
    # Only closed fixture vocabulary crosses the persistence boundary.
    values = {
        "north",
        "south",
        "north-guide",
        "community-note",
        "support",
        "reset",
        "policy",
        "hours",
        "unknown-id",
    }
    return {
        "user": event.user if event.user == "reader" else "other",
        "tool": event.tool
        if event.tool in {"read", "search", "account", "ticket", "admin"}
        else "other",
        "actor": event.actor if event.actor in {"support", "supervisor", "deputy"} else "other",
        "tenant": event.tenant if event.tenant in {"north", "south"} else "other",
        "arguments": {
            "value": event.arguments.get("value")
            if event.arguments.get("value") in values
            else "[withheld]"
        },
        "approved": event.approved,
        "status": event.status,
    }


def project(scenario: AttackScenario, observations: list[Observation]) -> dict:
    turns = []
    docs = {d.id for d in CORPUS} | {"uploaded-note"}
    for i, obs in enumerate(observations, 1):
        turns.append(
            {
                "turn": i,
                "decision": obs.decision,
                "response_chars": len(obs.text),
                "trace_channels": sorted({"tools", "documents"}.intersection(obs.model_fields_set)),
                "matched_rules": [r.kind for r in scenario.evaluation_rules if violates(r, obs)],
                "matched_synthetic_fields": [k for k, v in PRIVATE.items() if v in obs.text],
                "documents": [d if d in docs else "[withheld]" for d in obs.documents[:32]],
                "tools": [project_tool(t) for t in obs.tools],
                "tokens": obs.tokens,
            }
        )
    return {"request_steps": scenario.attack_steps, "turns": turns}
