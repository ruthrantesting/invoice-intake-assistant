"""Evaluate extraction against an externally maintained labeled JSONL corpus.

Each row must include `format`, `quality`, `expected` and `predicted` objects.
No invoice samples are bundled with the application.
"""

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

__all__ = ["score"]


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    corrections = 0
    comparisons = 0
    duplicate_counts = Counter()
    latencies: list[float] = []
    for row in rows:
        expected = row.get("expected", {})
        predicted = row.get("predicted", {})
        group = (str(row.get("format", "unknown")), str(row.get("quality", "unknown")))
        for key, expected_value in expected.items():
            comparisons += 1
            matched = predicted.get(key) == expected_value
            by_group[group]["correct" if matched else "incorrect"] += 1
            corrections += not matched
        expected_duplicate = bool(row.get("expected_duplicate", False))
        predicted_duplicate = bool(row.get("predicted_duplicate", False))
        duplicate_counts[
            "tp"
            if expected_duplicate and predicted_duplicate
            else "fn"
            if expected_duplicate
            else "fp"
            if predicted_duplicate
            else "tn"
        ] += 1
        if isinstance(row.get("latency_ms"), (int, float)) and row["latency_ms"] >= 0:
            latencies.append(float(row["latency_ms"]))
    per_group = {
        f"{file_format}/{quality}": {
            "accuracy": counts["correct"] / max(1, counts["correct"] + counts["incorrect"]),
            **dict(counts),
        }
        for (file_format, quality), counts in by_group.items()
    }
    precision = duplicate_counts["tp"] / max(1, duplicate_counts["tp"] + duplicate_counts["fp"])
    recall = duplicate_counts["tp"] / max(1, duplicate_counts["tp"] + duplicate_counts["fn"])
    sorted_latencies = sorted(latencies)
    p95_index = (
        min(len(sorted_latencies) - 1, max(0, int(0.95 * len(sorted_latencies) + 0.999) - 1))
        if sorted_latencies
        else 0
    )
    return {
        "field_accuracy_by_format_quality": per_group,
        "correction_share": corrections / max(1, comparisons),
        "duplicate_precision": precision,
        "duplicate_recall": recall,
        "latency_ms": {
            "sample_count": len(latencies),
            "median": statistics.median(latencies) if latencies else None,
            "p95": sorted_latencies[p95_index] if sorted_latencies else None,
        },
        "records": len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "corpus", type=Path, help="Path to labeled JSON Lines data, stored securely"
    )
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.corpus.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(json.dumps(score(rows), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
