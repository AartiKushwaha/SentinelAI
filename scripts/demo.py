"""Run a paired, offline assessment against the local API and export its reports."""

import argparse
import time
from pathlib import Path

import httpx


def run_demo(port: int, output: Path, scenario_ids: list[str] | None) -> None:
    with httpx.Client(
        base_url=f"http://127.0.0.1:{port}/api/v1", timeout=20, trust_env=False
    ) as client:
        for mode in ("vulnerable", "secured"):
            target = (
                client.post(
                    "/targets",
                    json={"name": f"Support lab {mode}", "kind": "mcp_agent", "mode": mode},
                )
                .raise_for_status()
                .json()
            )
            run = (
                client.post(
                    "/assessments", json={"target_id": target["id"], "scenario_ids": scenario_ids}
                )
                .raise_for_status()
                .json()
            )
            path = "/assessments/" + run["id"]
            deadline = time.monotonic() + 120
            while True:
                state = client.get(path).raise_for_status().json()
                if state["status"] not in ("queued", "running"):
                    break
                if time.monotonic() >= deadline:
                    client.post(path + "/cancel").raise_for_status()
                    raise TimeoutError("Demo exceeded two minutes and was cancelled")
                time.sleep(0.2)
            if state["status"] != "completed":
                raise RuntimeError(f"Assessment ended with status {state['status']}")
            directory = output / run["id"]
            directory.mkdir(parents=True, exist_ok=True)
            for fmt, extension in (("json", "json"), ("markdown", "md"), ("html", "html")):
                report = client.get(path + "/report", params={"format": fmt}).raise_for_status()
                (directory / f"report.{extension}").write_bytes(report.content)
            m = state["metrics"]
            print(
                f"{mode:10} {m['executed']} executed | {m['passed']} pass | {m['failed']} fail | {m['inconclusive']} inconclusive | {m['errors']} error | ASR {m['asr']}"
            )
            print(directory.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenario_ids",
        help="Select one ID, repeat to select more",
    )
    args = parser.parse_args()
    run_demo(args.port, args.output, args.scenario_ids)
