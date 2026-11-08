#!/usr/bin/env python3
import argparse
import json
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct one pre-authorisation run")
    parser.add_argument("run_id")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    url = f"{args.base_url.rstrip('/')}/v1/runs/{args.run_id}/trace"
    with urllib.request.urlopen(url, timeout=10) as response:
        trace = json.load(response)
    print(f"run={trace['run_id']} correlation={trace['correlation_id']}")
    for step in trace["steps"]:
        payload = json.dumps(step["payload"], ensure_ascii=False, sort_keys=True)
        print(f"{step['sequence']:02d} {step['agent']:<20} {step['kind']:<16} {payload}")
    print("cost ledger")
    for cost in trace.get("costs", []):
        print(json.dumps(cost, sort_keys=True))


if __name__ == "__main__":
    main()
