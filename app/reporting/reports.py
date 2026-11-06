from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Assessment,
    AttackExecution,
    Definition,
    Evaluation,
    Finding,
    Selection,
)
from app.evaluation.metrics import measures


def snapshot(db: Session, run: Assessment) -> dict:
    stmt = (
        select(Selection, Definition, AttackExecution, Evaluation, Finding)
        .join(Definition, Selection.definition_id == Definition.id)
        .outerjoin(AttackExecution, Selection.id == AttackExecution.selection_id)
        .outerjoin(Evaluation, AttackExecution.id == Evaluation.execution_id)
        .outerjoin(Finding, AttackExecution.id == Finding.execution_id)
        .where(Selection.assessment_id == run.id)
        .order_by(Selection.position)
    )
    coverage = []
    results = []
    findings = []
    severity_index: dict[str, list[str]] = defaultdict(list)
    category_index: dict[str, list[str]] = defaultdict(list)
    for item, definition, execution, evaluation, finding in db.execute(stmt):
        body = definition.body
        coverage.append(
            {
                "scenario_id": definition.scenario_id,
                "definition_sha256": definition.digest,
                "status": item.status,
                "category": body["category"],
            }
        )
        if execution and evaluation:
            results.append(
                {
                    "execution_id": str(execution.id),
                    "scenario_id": definition.scenario_id,
                    "category": body["category"],
                    "severity": body["severity"],
                    "latency": execution.latency,
                    "tokens": execution.tokens,
                    "attempts": execution.attempts,
                    **evaluation.details,
                    "review_status": evaluation.review_status,
                    "evidence": execution.evidence,
                }
            )
        if finding and evaluation:
            findings.append(
                {
                    "id": str(finding.id),
                    "assessment_id": str(run.id),
                    "target_id": str(run.target_id),
                    "timestamp": finding.created_at.isoformat(),
                    "review_status": evaluation.review_status,
                    "severity": finding.severity,
                    **finding.details,
                }
            )
            severity_index[finding.severity].append(str(finding.id))
            category_index[body["category"]].append(str(finding.id))
    metrics = measures(results, run.duration, run.config["price_per_million_tokens"])
    return {
        "assessment_id": str(run.id),
        "target_id": str(run.target_id),
        "started_at_utc": run.created_at.isoformat(),
        "status": run.status,
        "configuration": run.config,
        "executive_summary": f"{metrics['failed']} of {metrics['decided']} decided tests observed a policy violation. {metrics['inconclusive']} need more evidence and {metrics['errors']} encountered execution errors. {len(results)} of {len(coverage)} selected scenarios produced results.",
        "metrics": metrics,
        "coverage": coverage,
        "findings_by_severity": dict(severity_index),
        "findings_by_category": dict(category_index),
        "findings": findings,
        "executions": results,
        "limitations": [
            "ASR = FAIL / (PASS + FAIL). An empty denominator has no rate.",
            "Each finding describes one scenario on this target configuration. Overlapping probes may share one root cause.",
            "Target-supplied traces and denial signals require independent corroboration. Raw target output is withheld.",
        ],
    }
