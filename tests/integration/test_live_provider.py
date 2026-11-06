import asyncio
import os
import uuid

import pytest

from app.core.config import Settings
from app.evaluation.judge import HostedJudge
from app.targets.http import HttpTarget


@pytest.mark.skipif(
    os.environ.get("SENTINEL_TEST_LIVE_JUDGE") != "1",
    reason="requires explicitly authorized hosted judge",
)
async def test_configured_live_judge():
    settings = Settings()
    assert settings.provider == "hosted" and settings.judge_profile and settings.judge_model
    provider = HostedJudge(
        HttpTarget(settings.profiles[settings.judge_profile], settings), settings.judge_model
    )
    async with asyncio.timeout(settings.timeout):
        opinion = await provider.assess(
            "Return JSON with verdict INCONCLUSIVE, evidence_turn 1, reasoning explaining insufficient evidence and confidence 0.2. Turn 1 has no target output.",
            str(uuid.uuid4()),
        )
    assert opinion.evidence_turn == 1
