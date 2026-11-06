import asyncio
from dataclasses import dataclass, field
from time import perf_counter

from app.attacks.base import AttackModule
from app.attacks.registry import AttackScenario
from app.evaluation.rules import EvaluationResult, evaluate
from app.targets.base import (
    Interaction,
    Message,
    Observation,
    TargetAdapter,
    TargetError,
    TransientError,
)


@dataclass
class Trial:
    result: EvaluationResult
    observations: list[Observation] = field(default_factory=list)
    attempts: int = 0
    latency: float = 0


async def execute(
    scenario: AttackScenario,
    module: AttackModule,
    target: TargetAdapter,
    key: str,
    deadline_seconds: float,
    retries: int,
) -> Trial:
    start = perf_counter()
    history: list[Message] = []
    observations: list[Observation] = []
    attempts = 0
    try:
        for turn, prompt in enumerate(module.steps(scenario)):
            history.append(Message(role="user", content=prompt))
            request = Interaction(messages=history.copy(), request_id=f"{key}-{turn}")
            for attempt in range(retries + 1):
                attempts += 1
                try:
                    async with asyncio.timeout(deadline_seconds):
                        obs = await target.send(request)
                    break
                except TransientError:
                    if attempt == retries:
                        raise
                    await asyncio.sleep(0.1 * 2**attempt)
            observations.append(obs)
            history.append(Message(role="assistant", content=obs.text))
        result = evaluate(scenario, observations)
    except (TimeoutError, TargetError) as error:
        result = EvaluationResult(
            outcome="ERROR",
            explanation=f"Target interaction failed ({type(error).__name__}).",
            confidence=0,
        )
    return Trial(result, observations, attempts, perf_counter() - start)
