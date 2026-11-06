"""Read and operate the local, single-user SentinelAI API."""

import os

import httpx
import streamlit as st

st.set_page_config(page_title="SentinelAI | Assessment workbench", layout="wide")
port = int(os.environ.get("SENTINEL_DASHBOARD_API_PORT", "8000"))
base = f"http://127.0.0.1:{port}/api/v1"


def request(method, path, **kwargs):
    try:
        with httpx.Client(base_url=base, trust_env=False, timeout=15) as client:
            response = client.request(method, path, **kwargs)
        if response.is_error:
            st.error(
                f"Request failed ({response.status_code}): {response.json().get('error', {}).get('code', 'api_error')}"
            )
            st.stop()
        return response
    except httpx.HTTPError:
        st.error(f"Start the SentinelAI API on loopback port {port}, then refresh.")
        st.stop()


def all_rows(path):
    rows = []
    while True:
        page = request("GET", path, params={"offset": len(rows), "limit": 100}).json()
        rows.extend(page)
        if len(page) < 100:
            return rows


st.sidebar.title("SentinelAI")
page = st.sidebar.radio("Workbench", ["Overview", "Targets", "Scenario catalogue", "Assessments"])
if page == "Overview":
    st.title("Assessment overview")
    summary = request("GET", "/metrics/summary").json()
    outcomes = summary["outcomes"]
    cols = st.columns(4)
    for col, (label, value) in zip(
        cols,
        [
            ("Tests executed", summary["executed"]),
            ("Observed violations", outcomes.get("FAIL", 0)),
            ("Inconclusive", outcomes.get("INCONCLUSIVE", 0)),
            ("Execution errors", outcomes.get("ERROR", 0)),
        ],
        strict=True,
    ):
        col.metric(label, value)
    st.caption(
        "Each violation is one failed scenario. Several probes can expose the same root cause."
    )
    st.subheader("Recent assessments")
    st.dataframe(request("GET", "/assessments", params={"limit": 10}).json(), hide_index=True)
elif page == "Targets":
    st.title("Registered targets")
    with st.form("register"):
        name = st.text_input("Demo target name", max_chars=80)
        mode = st.radio("Security controls", ["secured", "vulnerable"], horizontal=True)
        if st.form_submit_button("Register demo target"):
            request("POST", "/targets", json={"name": name, "mode": mode, "kind": "mcp_agent"})
            st.success("Demo target registered.")
    st.dataframe(all_rows("/targets"), hide_index=True)
elif page == "Scenario catalogue":
    st.title("Scenario catalogue")
    cases = all_rows("/scenarios")
    categories = st.multiselect("Attack categories", sorted({s["category"] for s in cases}))
    for case in cases:
        if categories and case["category"] not in categories:
            continue
        with st.expander(f"{case['name']} · {case['severity']}"):
            st.write(case["description"])
            st.code("\n".join(case["attack_steps"]), language=None)
            st.write(case["remediation"])
            st.caption(case["id"])
else:
    st.title("Assessments")
    targets = {t["id"]: t["name"] for t in all_rows("/targets")}
    if targets:
        with st.form("launch"):
            target = st.selectbox(
                "Target", targets, format_func=lambda k: targets[k] + " · " + k[:8]
            )
            cases = all_rows("/scenarios")
            selected = st.multiselect(
                "Scenarios (empty selects all compatible probes)",
                [s["id"] for s in cases if s["enabled"]],
            )
            if st.form_submit_button("Start assessment"):
                new = request(
                    "POST",
                    "/assessments",
                    json={"target_id": target, "scenario_ids": selected or None},
                ).json()
                st.session_state["chosen_run"] = new["id"]
    else:
        st.info("Register a demo target in Targets to start an assessment.")
    history = all_rows("/assessments")
    if history:
        ids = [r["id"] for r in history]
        labels = {
            r["id"]: f"{r['created_at']} · {targets.get(r['target_id'], 'target')} · {r['status']}"
            for r in history
        }
        run_id = st.selectbox(
            "Assessment history", ids, format_func=lambda k: labels[k], key="chosen_run"
        )
        route = "/assessments/" + run_id
        run = request("GET", route).json()
        m = run["metrics"]
        total = len(run["scenarios"])
        st.progress(
            m["executed"] / total if total else 0,
            text=f"{run['status']} · {m['executed']} of {total} tests executed",
        )
        if run["status"] in ("queued", "running"):
            if st.button("Refresh progress"):
                st.rerun()
            if st.button("Cancel assessment"):
                request("POST", route + "/cancel")
                st.rerun()
        else:
            st.write(
                f"{m['passed']} passed · {m['failed']} observed violations · {m['inconclusive']} inconclusive · {m['errors']} errors"
            )
            first, second = st.columns(2)
            with first:
                st.subheader("Findings by severity")
                if m["finding_severities"]:
                    st.bar_chart(m["finding_severities"], horizontal=True)
                else:
                    st.caption("No violations observed.")
            with second:
                st.subheader("Attack success by category")
                st.dataframe(
                    [{"category": k, **v} for k, v in m["categories"].items()], hide_index=True
                )
                st.caption("ASR divides observed violations by decided tests (passed + failed).")
            st.subheader("Findings")
            findings = all_rows(route + "/findings")
            severity = st.multiselect("Severity", sorted({f["severity"] for f in findings}))
            for finding in findings:
                if severity and finding["severity"] not in severity:
                    continue
                with st.expander(f"{finding['severity']} · {finding['title']}"):
                    st.write(finding["explanation"])
                    st.write(finding["remediation"])
                    st.json(finding["evidence"])
            fmt = st.selectbox("Report format", ["json", "markdown", "html"])
            report = request("GET", route + "/report", params={"format": fmt})
            extension = "md" if fmt == "markdown" else fmt
            st.download_button(
                "Download report",
                report.content,
                f"sentinel-{run_id}.{extension}",
                mime=report.headers["content-type"],
            )
