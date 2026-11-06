import pytest

from app.attacks.registry import Registry
from app.core.config import Settings
from app.evaluation.judge import MockJudge, advise


async def test_judge_references_real_evidence():
    scenario = next(iter(Registry(Settings().scenario_dir).entries.values()))
    result = await advise(MockJudge(), scenario, [{"decision": None}], "abc", 0.8)
    assert result["review_required"] and not result["meets_threshold"]
    with pytest.raises(ValueError, match="missing evidence"):
        await advise(MockJudge(), scenario, [], "abc", 0.8)
