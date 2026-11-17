"""Calibrate semantic retrieval; this small synthetic set is demo evidence only."""
import json
from pathlib import Path
from preauth.config import get_settings
from preauth.rag.embeddings import MiniLMEmbedder


def main():
    model = MiniLMEmbedder(get_settings().local_embedding_model)
    fixture = json.loads(Path("evals/precedent_pairs.json").read_text())
    scored = {}
    for split, pairs in fixture.items():
        rows = []
        for left, right, same in pairs:
            vectors = model.encode([left, right])
            rows.append({"score": float(vectors[0] @ vectors[1]), "same": same})
        scored[split] = rows
    negatives = [row["score"] for row in scored["calibration"] if not row["same"]]
    # Search a declared 0.01 grid using calibration data only. Among thresholds
    # with zero false matches, maximize positive recall, then prefer the highest
    # threshold. Held-out labels never select the threshold.
    candidates = []
    for tick in range(50, 100):
        value = tick / 100
        rows = scored["calibration"]
        if any(row["score"] >= value and not row["same"] for row in rows):
            continue
        recall_count = sum(row["score"] >= value and row["same"] for row in rows)
        candidates.append((recall_count, value))
    threshold = max(candidates)[1] if candidates else 1.0
    held = scored["held_out"]
    false_matches = sum(row["score"] >= threshold and not row["same"] for row in held)
    true_matches = sum(row["score"] >= threshold and row["same"] for row in held)
    result = {"embedding_model": model.name, "threshold": threshold,
              "passed": false_matches == 0 and true_matches > 0, "scores": scored,
              "held_out_false_matches": false_matches, "held_out_true_matches": true_matches,
              "threshold_method": "0.01 grid; zero calibration false matches; max recall then highest threshold",
              "limitation": "Small synthetic demo set; not a production validation."}
    Path("evals/precedent_calibration.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit("Calibration failed; automation stays disabled")


if __name__ == "__main__":
    main()
