import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prefixes", nargs="+")
    parser.add_argument("--out", default="loadtest/results/summary.json")
    args = parser.parse_args()
    rows = []
    for prefix in args.prefixes:
        stats_path = Path(f"{prefix}_stats.csv")
        with stats_path.open(newline="", encoding="utf-8") as handle:
            stats = list(csv.DictReader(handle))
        e2e = next(row for row in stats if row["Type"] == "E2E" and row["Name"] == "preauth terminal")
        failures = int(e2e["Failure Count"])
        requests = int(e2e["Request Count"])
        label = Path(prefix).name
        rows.append(
            {
                "label": label,
                "completed_runs": requests,
                "rps": float(e2e["Requests/s"]),
                "p50_ms": float(e2e["50%"]),
                "p95_ms": float(e2e["95%"]),
                "error_rate": round(failures / max(requests, 1), 4),
                "slo_met": float(e2e["95%"] or 0) <= 10000 and failures / max(requests, 1) < 0.01,
            }
        )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
