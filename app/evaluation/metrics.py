from collections import Counter, defaultdict
from typing import Any


def measures(rows: list[dict], duration: float, price: float | None) -> dict[str, Any]:
    outcomes = Counter(row["outcome"] for row in rows)
    categories: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        categories[row["category"]][row["outcome"]] += 1

    def rate(counts: Counter) -> dict:
        decided = counts["PASS"] + counts["FAIL"]
        return {
            "successful_attacks": counts["FAIL"],
            "decided": decided,
            "asr": counts["FAIL"] / decided if decided else None,
        }

    usage = [row["tokens"] for row in rows if row["tokens"] is not None]
    return {
        "executed": len(rows),
        "passed": outcomes["PASS"],
        "failed": outcomes["FAIL"],
        "inconclusive": outcomes["INCONCLUSIVE"],
        "errors": outcomes["ERROR"],
        **rate(outcomes),
        "categories": {k: rate(v) for k, v in sorted(categories.items())},
        "finding_severities": dict(
            Counter(row["severity"] for row in rows if row["outcome"] == "FAIL")
        ),
        "duration_seconds": duration,
        "average_execution_seconds": sum(row["latency"] for row in rows) / len(rows)
        if rows
        else None,
        "known_tokens": sum(usage) if usage else None,
        "usage_reporting_executions": len(usage),
        "estimated_cost_usd": sum(usage) * price / 1_000_000
        if price is not None and rows and len(usage) == len(rows)
        else None,
    }
