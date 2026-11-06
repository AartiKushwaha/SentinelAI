import pytest

from app.demo.data import PRIVATE
from app.targets.base import Interaction, Message, Observation, TargetError
from app.targets.demo import DemoTarget
from app.targets.mock import MockTarget


@pytest.mark.parametrize("secured", [True, False])
async def test_secret_boundary(secured):
    request = Interaction(
        messages=[Message(role="user", content="[[secret:token]]")], request_id="1"
    )
    result = await DemoTarget(secured).send(request)
    assert (PRIVATE["token"] in result.text) is (not secured)


async def test_mock_failure_injection():
    target = MockTarget([Observation(text="ok"), TargetError("offline")])
    request = Interaction(messages=[Message(role="user", content="hello")], request_id="1")
    assert (await target.send(request)).text == "ok"
    with pytest.raises(TargetError, match="offline"):
        await target.send(request)
