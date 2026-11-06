import pytest

from app.attacks.base import ConversationModule
from app.attacks.registry import Registry
from app.core.config import Settings
from app.demo.lab import SecurityLab
from app.demo.retrieval import LexicalRetriever
from app.demo.tools import ToolServer
from app.orchestration.execution import execute

cases = [
    s
    for s in Registry(Settings().scenario_dir).entries.values()
    if s.target_requirements != {"chat"}
]


@pytest.mark.parametrize("scenario", cases, ids=lambda s: s.id)
@pytest.mark.parametrize("secured", [True, False])
async def test_lab(scenario, secured):
    trial = await execute(scenario, ConversationModule(), SecurityLab(secured), "pair", 2, 0)
    assert trial.result.outcome == ("PASS" if secured else "FAIL")


def test_tool_approval_and_unknown_tool():
    server = ToolServer(True)
    event, _ = server.invoke("ticket", "support", "support")
    assert event.status == "denied" and not server.tickets
    assert server.invoke("ticket", "support", "support", approved=True)[0].status == "executed"
    assert server.tickets == ["support"]
    assert ToolServer(False).invoke("shell", "anything", "support")[0].status == "denied"


def test_retrieval_applies_acl_before_ranking():
    retriever = LexicalRetriever()
    assert retriever.search("payroll", "north", True) == []
    assert [d.id for d in retriever.search("hours", "north", True)] == ["north-guide"]
