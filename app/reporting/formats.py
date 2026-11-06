import html
import json
import re


def render(report: dict, fmt: str) -> str:
    """Build print-friendly human reports from the same persisted projection as JSON."""
    if fmt == "json":
        return json.dumps(report, indent=2, sort_keys=True)
    if fmt not in {"html", "markdown"}:
        raise ValueError("unknown format")
    markup = fmt == "html"
    parts: list[str] = []

    def escape(text: object) -> str:
        line = html.escape(" ".join(str(text).splitlines()))
        return line if markup else re.sub(r"([\\`*_{}\[\]()#+!|~])", r"\\\1", line)

    def heading(level: int, title: str) -> None:
        safe = escape(title)
        parts.append(f"<h{level}>{safe}</h{level}>" if markup else f"{'#' * level} {safe}")

    def paragraph(value: str) -> None:
        safe = escape(value)
        parts.append(f"<p>{safe}</p>" if markup else safe)

    def table(headers: list[str], rows: list[list]) -> None:
        if markup:
            head = "".join("<th>" + escape(h) + "</th>" for h in headers)
            body = "".join(
                "<tr>" + "".join("<td>" + escape(v) + "</td>" for v in row) + "</tr>"
                for row in rows
            )
            parts.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
        else:
            lines = [headers, ["---"] * len(headers), *rows]
            parts.append(
                "\n".join("| " + " | ".join(escape(v) for v in row) + " |" for row in lines)
            )

    def evidence(value: object) -> None:
        code = json.dumps(value, indent=2, sort_keys=True)
        parts.append(
            "<pre>" + html.escape(code) + "</pre>"
            if markup
            else "\n".join("    " + line for line in code.splitlines())
        )

    heading(1, "SentinelAI assessment report")
    paragraph(report["executive_summary"])
    cfg = report["configuration"]
    metrics = report["metrics"]
    table(
        ["Assessment", "Target", "Started (UTC)", "Status"],
        [
            [
                report["assessment_id"],
                cfg.get("target_name", report["target_id"]),
                report["started_at_utc"],
                report["status"],
            ]
        ],
    )
    heading(2, "Assessment metrics")
    table(
        ["Measure", "Value"],
        [
            [k.replace("_", " "), v if v is not None else "Unavailable"]
            for k, v in metrics.items()
            if not isinstance(v, dict)
        ],
    )
    heading(2, "Results by attack category")
    table(
        ["Category", "Observed violations", "Decided", "ASR"],
        [
            [
                name,
                group["successful_attacks"],
                group["decided"],
                f"{group['asr']:.1%}" if group["asr"] is not None else "Unavailable",
            ]
            for name, group in metrics.get("categories", {}).items()
        ],
    )
    heading(2, "Findings by severity")
    if not report["findings"]:
        paragraph("No scenario produced a finding.")
    for severity in ("Critical", "High", "Medium", "Low", "Informational"):
        group = [f for f in report["findings"] if f["severity"] == severity]
        if group:
            heading(3, f"{severity} ({len(group)})")
        for f in group:
            heading(4, f["title"])
            paragraph(f["explanation"])
            paragraph(f["impact"])
            paragraph(f["remediation"])
            table(
                ["Scenario", "Category", "Confidence", "Review"],
                [[f["scenario_id"], f["category"], f["confidence"], f["review_status"]]],
            )
            paragraph(f["setup"])
            evidence(f["evidence"])
            paragraph("Framework guidance · " + " / ".join(f["references"]))
            paragraph("Finding " + f["id"] + " · " + f["timestamp"] + " UTC")
    heading(2, "Findings by category")
    for category in report["findings_by_category"]:
        paragraph(
            category
            + " · "
            + ", ".join(f["title"] for f in report["findings"] if f["category"] == category)
        )
    heading(2, "Inconclusive tests and errors")
    open_results = [r for r in report["executions"] if r["outcome"] in {"INCONCLUSIVE", "ERROR"}]
    if open_results:
        table(
            ["Scenario", "Outcome", "Reason", "Review"],
            [
                [r["scenario_id"], r["outcome"], r["explanation"], r["review_status"]]
                for r in open_results
            ],
        )
    else:
        paragraph("None recorded.")
    heading(2, "Scenario coverage")
    outcomes = {r["scenario_id"]: r["outcome"] for r in report["executions"]}
    table(
        ["Scenario", "Status", "Outcome"],
        [
            [c["scenario_id"], c["status"], outcomes.get(c["scenario_id"], "Unexecuted")]
            for c in report["coverage"]
        ],
    )
    heading(2, "Run configuration")
    paragraph("Target " + report["target_id"])
    evidence(cfg)
    heading(2, "Limitations")
    for limit in report["limitations"]:
        paragraph(limit)
    content = "\n\n".join(parts)
    if markup:
        return (
            '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SentinelAI assessment</title><style>body{max-width:84ch;margin:3rem auto;padding:1rem;font:16px/1.55 system-ui;color:#19333c}h1,h2,h3,h4{line-height:1.2}h2{margin-top:2em;border-bottom:2px solid #42837e;padding-bottom:.3em}table{border-collapse:collapse;width:100%;font-size:.9rem}td,th{padding:.5em;text-align:left;border-bottom:1px solid #ccd8da;overflow-wrap:anywhere}pre{background:#edf3f4;padding:1rem;white-space:pre-wrap;overflow-wrap:anywhere}@media print{h2,h3,h4{break-after:avoid}}</style><main>'
            + content
            + "</main></html>"
        )
    return content + "\n"
