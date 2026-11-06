import asyncio
import logging
from collections import deque
from time import monotonic, perf_counter
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select, update

from app.api.schemas import Problem, StartAssessment
from app.attacks.base import AttackModule, ConversationModule
from app.attacks.registry import AttackScenario, Category, Registry
from app.core.config import Settings
from app.core.security import digest
from app.database.models import (
    Assessment,
    AttackExecution,
    Audit,
    Definition,
    Evaluation,
    Finding,
    Selection,
    Target,
)
from app.database.store import Store
from app.demo.lab import SecurityLab
from app.evaluation.evidence import project
from app.evaluation.judge import HostedJudge, JudgeProvider, MockJudge, advise
from app.evaluation.rules import EvaluationResult
from app.orchestration.execution import Trial, execute
from app.targets.base import TargetAdapter, TargetError
from app.targets.http import HttpTarget

log = logging.getLogger("sentinel.jobs")
ACTIVE = ("queued", "running")


class Scheduler:
    """Single event-loop owner. A durable queue can implement the same submit/cancel boundary."""

    def __init__(self, settings: Settings, store: Store, registry: Registry):
        self.cfg = settings
        self.store = store
        self.registry = registry
        self.jobs: dict[UUID, asyncio.Task] = {}
        self.starts: deque[float] = deque()
        self.slots = asyncio.Semaphore(settings.concurrency)
        self.modules: dict[Category, AttackModule] = {c: ConversationModule() for c in Category}
        self.http = {k: HttpTarget(v, settings) for k, v in settings.profiles.items()}
        self.judge: JudgeProvider | None = None
        if settings.provider == "hosted":
            if settings.judge_profile not in self.http or not settings.judge_model:
                raise ValueError("hosted judge requires a named profile and model")
            self.judge = HostedJudge(self.http[str(settings.judge_profile)], settings.judge_model)
        elif settings.provider == "mock":
            self.judge = MockJudge()

    def recover(self) -> None:
        with self.store.session.begin() as db:
            interrupted = select(Assessment.id).where(Assessment.status.in_(ACTIVE))
            db.execute(
                update(Selection)
                .where(
                    Selection.assessment_id.in_(interrupted),
                    Selection.status.in_(("pending", "running")),
                )
                .values(status="interrupted")
            )
            db.execute(
                update(Assessment).where(Assessment.status.in_(ACTIVE)).values(status="interrupted")
            )

    def submit(self, request: StartAssessment) -> UUID:
        while self.starts and self.starts[0] <= monotonic() - 60:
            self.starts.popleft()
        if len(self.jobs) >= self.cfg.max_active or len(self.starts) >= self.cfg.creates_per_minute:
            raise Problem(429, "assessment_capacity")
        with self.store.session.begin() as db:
            target = db.get(Target, request.target_id)
            if target is None:
                raise Problem(404, "target_not_found")
            config = target.config
            remote = config["adapter"] == "http"
            profile = self.cfg.profiles.get(config.get("profile") or "")
            if remote and (
                not profile
                or not config.get("authorized")
                or config["profile_digest"] != digest(profile.model_dump(mode="json"))
            ):
                raise Problem(409, "profile_changed_register_again")
            capabilities = (
                profile.capabilities if remote and profile else {"rag", "tools", "agent", "chat"}
            )
            ids = request.scenario_ids
            if ids and (
                len(set(ids)) != len(ids) or any(i not in self.registry.entries for i in ids)
            ):
                raise Problem(422, "invalid_scenario_selection")
            pool = (
                [self.registry.entries[i] for i in ids] if ids else self.registry.entries.values()
            )
            selected = [
                s
                for s in pool
                if s.enabled
                and s.target_requirements <= capabilities
                and (not request.category or s.category == request.category)
                and (not request.severity or s.severity == request.severity)
            ]
            if not selected or (ids and len(selected) != len(ids)):
                raise Problem(422, "empty_or_incompatible_selection")
            limit = min(request.concurrency or self.cfg.concurrency, self.cfg.concurrency)
            run = Assessment(
                target_id=target.id,
                config={
                    "target": config,
                    "target_name": target.name,
                    "concurrency": limit,
                    "registry_size": len(self.registry.entries),
                    "timeout": self.cfg.timeout,
                    "retries": self.cfg.retries if remote and profile and profile.idempotent else 0,
                    "provider": self.cfg.provider,
                    "judge_model": self.cfg.judge_model,
                    "judge_profile": self.cfg.judge_profile,
                    "min_confidence": self.cfg.min_confidence,
                    "price_per_million_tokens": self.cfg.price_per_million_tokens,
                    "fixture_version": "v1",
                    "evaluator": "deterministic-v1",
                },
            )
            db.add(run)
            db.flush()
            ids_work = []
            for position, scenario in enumerate(selected):
                body = scenario.model_dump(mode="json")
                body["target_requirements"] = sorted(body["target_requirements"])
                signature = digest(body)
                definition = db.scalar(select(Definition).where(Definition.digest == signature))
                if definition is None:
                    definition = Definition(digest=signature, scenario_id=scenario.id, body=body)
                    db.add(definition)
                    db.flush()
                item = Selection(
                    assessment_id=run.id, definition_id=definition.id, position=position
                )
                db.add(item)
                db.flush()
                ids_work.append((item.id, scenario))
        self.starts.append(monotonic())
        task = asyncio.create_task(self.run(run.id, run.config, ids_work))
        self.jobs[run.id] = task
        task.add_done_callback(lambda done: self.jobs.pop(run.id, None))
        return run.id

    async def stop(self, run_id: UUID) -> None:
        task = self.jobs.get(run_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                # A task cancelled before its first instruction never enters run's finally.
                self.finish(run_id, "cancelled", None)

    async def close(self) -> None:
        await asyncio.gather(*(self.stop(id_) for id_ in list(self.jobs)))

    def finish(self, run_id: UUID, status: str, elapsed: float | None) -> None:
        with self.store.session.begin() as db:
            values: dict = {"status": status}
            if elapsed is not None:
                values["duration"] = elapsed
            db.execute(update(Assessment).where(Assessment.id == run_id).values(**values))
            db.execute(
                update(Selection)
                .where(
                    Selection.assessment_id == run_id, Selection.status.in_(("pending", "running"))
                )
                .values(status=status)
            )

    async def run(self, run_id: UUID, cfg: dict, work: list[tuple[UUID, AttackScenario]]) -> None:
        started = perf_counter()
        status = "completed"
        limit = asyncio.Semaphore(cfg["concurrency"])

        async def one(item_id: UUID, scenario: AttackScenario) -> None:
            async with limit, self.slots:
                with self.store.session.begin() as db:
                    db.execute(
                        update(Selection).where(Selection.id == item_id).values(status="running")
                    )
                try:
                    target: TargetAdapter
                    if cfg["target"]["adapter"] == "demo":
                        target = SecurityLab(
                            cfg["target"]["mode"] == "secured",
                            set(cfg["target"]["forbidden_actions"]),
                        )
                    else:
                        target = self.http[cfg["target"]["profile"]]
                    trial = await execute(
                        scenario,
                        self.modules[scenario.category],
                        target,
                        str(item_id),
                        cfg["timeout"],
                        cfg["retries"],
                    )
                except Exception as error:
                    log.error("scenario_failed", extra={"failure_type": type(error).__name__})
                    trial = Trial(
                        EvaluationResult(
                            outcome="ERROR",
                            explanation="Unexpected adapter or evaluation failure.",
                            confidence=0,
                        )
                    )
                evidence = project(scenario, trial.observations)
                if (
                    trial.result.outcome == "PASS"
                    and trial.result.confidence < cfg["min_confidence"]
                ):
                    trial.result = EvaluationResult(
                        outcome="INCONCLUSIVE",
                        explanation="Secure evidence fell below the configured confidence threshold.",
                        confidence=trial.result.confidence,
                    )
                if self.judge and trial.result.outcome == "INCONCLUSIVE" and evidence["turns"]:
                    try:
                        async with asyncio.timeout(cfg["timeout"]):
                            trial.result.advisor = await advise(
                                self.judge,
                                scenario,
                                evidence["turns"],
                                str(item_id) + "-judge",
                                cfg["min_confidence"],
                            )
                    except (TimeoutError, TargetError, ValueError, ValidationError) as error:
                        trial.result.advisor = {
                            "status": "unavailable",
                            "reason": type(error).__name__,
                        }
                self.persist(run_id, item_id, scenario, trial, evidence)
                await asyncio.sleep(0)

        try:
            with self.store.session.begin() as db:
                db.execute(
                    update(Assessment).where(Assessment.id == run_id).values(status="running")
                )
            async with asyncio.TaskGroup() as group:
                for item_id, scenario in work:
                    group.create_task(one(item_id, scenario))
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        except Exception as error:
            log.error("run_failed", extra={"failure_type": type(error).__name__})
            status = "interrupted"
        finally:
            self.finish(run_id, status, perf_counter() - started)

    def persist(
        self, run_id: UUID, item_id: UUID, scenario: AttackScenario, trial: Trial, evidence: dict
    ) -> None:
        result = trial.result
        with self.store.session.begin() as db:
            usage = [o.tokens for o in trial.observations]
            execution = AttackExecution(
                selection_id=item_id,
                evidence=evidence,
                latency=trial.latency,
                attempts=trial.attempts,
                tokens=sum(t for t in usage if t is not None)
                if usage and None not in usage and trial.attempts == len(usage)
                else None,
            )
            db.add(execution)
            db.flush()
            db.add(
                Evaluation(
                    execution_id=execution.id,
                    outcome=result.outcome,
                    details=result.model_dump(),
                    review_status="pending"
                    if result.outcome in {"INCONCLUSIVE", "FAIL"}
                    else "unneeded",
                )
            )
            for turn in evidence["turns"]:
                for tool in turn["tools"]:
                    db.add(Audit(execution_id=execution.id, details={"turn": turn["turn"], **tool}))
            if result.outcome == "FAIL":
                db.add(
                    Finding(
                        execution_id=execution.id,
                        assessment_id=run_id,
                        severity=scenario.severity,
                        details={
                            "title": scenario.name,
                            "description": scenario.description,
                            "scenario_id": scenario.id,
                            "category": scenario.category.value,
                            "confidence": result.confidence,
                            "impact": scenario.impact,
                            "remediation": scenario.remediation,
                            "references": scenario.references,
                            "reproduction": scenario.attack_steps,
                            "setup": scenario.setup,
                            "evidence": evidence,
                            "explanation": result.explanation,
                        },
                    )
                )
            db.execute(update(Selection).where(Selection.id == item_id).values(status="finished"))
