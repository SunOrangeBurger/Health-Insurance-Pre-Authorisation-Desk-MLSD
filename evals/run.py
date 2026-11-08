import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

import httpx


TERMINAL = {"completed", "escalated", "degraded", "failed"}


def load_set(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def run_scenario(
    client: httpx.AsyncClient,
    scenario: dict[str, Any],
    prompt_version: str,
    poll_interval: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    response = await client.post(
        "/v1/preauth",
        json=scenario["request"],
        headers={
            "X-Client-ID": f"eval-{prompt_version}-{scenario['id']}",
            "X-Correlation-ID": f"eval-{prompt_version}-{scenario['id']}",
            "X-Research-Prompt-Version": prompt_version,
        },
    )
    response.raise_for_status()
    run_id = response.json()["run_id"]
    while True:
        run_response = await client.get(f"/v1/runs/{run_id}")
        run_response.raise_for_status()
        run = run_response.json()
        if run["status"] in TERMINAL:
            break
        await asyncio.sleep(poll_interval)
    trace_response = await client.get(f"/v1/runs/{run_id}/trace")
    trace_response.raise_for_status()
    return score_scenario(scenario, run, trace_response.json(), time.perf_counter() - started)


def score_scenario(
    scenario: dict[str, Any], run: dict[str, Any], trace: dict[str, Any], latency: float
) -> dict[str, Any]:
    result = run.get("result") or {}
    citations = result.get("citations") or []
    actual_clause_ids = list(dict.fromkeys(item.get("id") for item in citations if item.get("id")))
    expected_clause_ids = scenario.get("expected_clause_ids", [])
    expected_set = set(expected_clause_ids)
    actual_set = set(actual_clause_ids)
    required_recall = len(expected_set & actual_set) / len(expected_set) if expected_set else 1.0
    context_relevance = len(expected_set & actual_set) / len(actual_set) if actual_set else (1.0 if not expected_set else 0.0)
    invented = [item for item in citations if not item.get("id") or not item.get("text")]
    citation_resolution = 1.0 if not invented else 0.0
    verification = result.get("verification", {}).get("passed", False)
    safe_escalation = result.get("route") == "medical-review" and not verification
    groundedness = 1.0 if (safe_escalation or (verification and citation_resolution and citations)) else 0.0
    faithfulness = 1.0 if (safe_escalation or (verification and required_recall == 1.0)) else 0.0
    routing_correct = result.get("route") == scenario["expected_route"]
    position_correct = (
        not scenario.get("expected_position")
        or result.get("coverage_position") == scenario["expected_position"]
    )
    return {
        "id": scenario["id"],
        "category": scenario["category"],
        "run_id": run["run_id"],
        "status": run["status"],
        "expected_route": scenario["expected_route"],
        "actual_route": result.get("route"),
        "expected_position": scenario.get("expected_position"),
        "actual_position": result.get("coverage_position"),
        "expected_clause_ids": expected_clause_ids,
        "actual_clause_ids": actual_clause_ids,
        "routing_correct": routing_correct,
        "position_correct": position_correct,
        "groundedness": groundedness,
        "context_relevance": context_relevance,
        "faithfulness": faithfulness,
        "required_clause_recall": required_recall,
        "citation_resolution": citation_resolution,
        "hallucinated": groundedness < 1.0,
        "invented_provisions": len(invented),
        "false_approval": result.get("route") == "approve-recommended"
        and scenario["expected_route"] != "approve-recommended",
        "correct_escalation": scenario["expected_route"] == "medical-review"
        and result.get("route") == "medical-review",
        "steps": len(trace.get("steps", [])),
        "tool_calls": len([item for item in trace.get("steps", []) if item["kind"] == "tool_call"]),
        "latency_seconds": round(latency, 4),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    mean = lambda key: round(sum(float(row[key]) for row in rows) / count, 4)
    escalation_rows = [row for row in rows if row["expected_route"] == "medical-review"]
    return {
        "scenarios": count,
        "routing_accuracy": mean("routing_correct"),
        "position_accuracy": mean("position_correct"),
        "groundedness": mean("groundedness"),
        "context_relevance": mean("context_relevance"),
        "faithfulness": mean("faithfulness"),
        "required_clause_recall": mean("required_clause_recall"),
        "citation_resolution_rate": mean("citation_resolution"),
        "hallucination_rate": round(sum(row["hallucinated"] for row in rows) / count, 4),
        "invented_provisions": sum(row["invented_provisions"] for row in rows),
        "correct_escalation_rate": round(
            sum(row["correct_escalation"] for row in escalation_rows) / len(escalation_rows), 4
        ) if escalation_rows else 1.0,
        "false_approval_rate": round(sum(row["false_approval"] for row in rows) / count, 4),
        "mean_latency_seconds": round(sum(row["latency_seconds"] for row in rows) / count, 4),
    }


async def async_main(args: argparse.Namespace) -> int:
    scenarios = load_set(Path(args.set))
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:
        rows = []
        for scenario in scenarios:
            row = await run_scenario(client, scenario, args.prompt_version, args.poll_interval)
            rows.append(row)
            print(f"{row['id']}: {row['actual_route']} route_ok={row['routing_correct']}")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "set": args.set,
        "prompt_version": args.prompt_version,
        "judge": "deterministic citation/route scorer v1",
        "judge_limitations": "Absence and entailment are approximated from verification state and expected clause IDs; ten cases require human spot-checking.",
        "metrics": aggregate(rows),
        "scenarios": rows,
    }
    output = Path(args.out) if args.out else Path("evals/results") / f"eval_{args.prompt_version}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"wrote {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="evals/set_v1.jsonl")
    parser.add_argument("--prompt-version", choices=("v1", "v2"), default="v2")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--poll-interval", type=float, default=0.1)
    parser.add_argument("--out")
    return asyncio.run(async_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
