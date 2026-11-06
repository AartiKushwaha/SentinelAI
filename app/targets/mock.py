from collections.abc import Iterable

from app.targets.base import Interaction, Observation, TargetError


class MockTarget:
    def __init__(self, observations: Iterable[Observation | TargetError]):
        self.responses = iter(observations)
        self.requests: list[Interaction] = []

    async def send(self, request: Interaction) -> Observation:
        self.requests.append(request)
        response = next(self.responses, None)
        if response is None:
            raise TargetError("mock_sequence_exhausted")
        if isinstance(response, TargetError):
            raise response
        return response
