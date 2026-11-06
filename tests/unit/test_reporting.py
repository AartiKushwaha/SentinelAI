from app.evaluation.metrics import measures
from app.reporting.formats import render


def test_asr_and_usage():
    rows = [
        dict(category="rag", severity="High", latency=0.2, tokens=10, outcome=o)
        for o in ("FAIL", "PASS", "INCONCLUSIVE", "ERROR")
    ]
    m = measures(rows, 1, 2)
    assert m["asr"] == 0.5 and m["decided"] == 2 and m["executed"] == 4
    assert m["estimated_cost_usd"] == 0.00008
    assert m["finding_severities"] == {"High": 1}
    assert measures(rows[2:], 1, None)["asr"] is None
    rows[0]["tokens"] = None
    assert measures(rows, 1, 2)["estimated_cost_usd"] is None


def test_html_escaping():
    doc = dict(
        assessment_id="1",
        target_id="2",
        started_at_utc="",
        status="completed",
        configuration={},
        metrics={},
        coverage=[],
        findings_by_severity={},
        findings_by_category={},
        findings=[],
        executions=[],
        limitations=[],
        executive_summary="<script>alert(1)</script>",
    )
    assert "<script>" not in render(doc, "html")
