# /// script
# dependencies = []
# ///
"""Compare experiment metrics against a baseline to detect regressions.

Loads a current metrics.json and a baseline metrics.json, computes deltas
for each (mode, difficulty, metric) triple, and reports regressions based
on configurable thresholds. Returns exit code 1 if any regression is found.

Usage:
    uv run python compare_baseline.py \
        --current /path/to/experiment/metrics.json \
        --baseline /path/to/baseline/metrics.json \
        [--threshold 0.05] \
        [--thresholds-file /path/to/thresholds.json] \
        [--strict] \
        [--output /path/to/comparison.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentlayer.logging import configure_logging, get_logger

logger = get_logger(__name__)

# Fields in metrics.json that are not quality metrics and should be skipped.
SKIP_FIELDS = frozenset({"count"})


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class MetricComparison:
    """Result of comparing a single metric between baseline and current."""

    mode: str
    difficulty: str
    metric: str
    baseline: float
    current: float
    delta: float
    threshold: float
    status: str  # "OK", "REGRESSED", "IMPROVED"


@dataclass
class ComparisonReport:
    """Aggregate comparison report across all metrics."""

    timestamp: str
    baseline_path: str
    current_path: str
    threshold: float
    regressions: list[dict[str, Any]] = field(default_factory=list)
    improvements: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[dict[str, Any]] = field(default_factory=list)
    passed: bool = True


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_metrics(path: Path) -> dict[str, Any]:
    """Load and validate a metrics.json file."""
    if not path.exists():
        logger.error("Metrics file not found: %s", path)
        sys.exit(2)
    with open(path) as f:
        data = json.load(f)
    if "by_mode" not in data:
        logger.error("Invalid metrics format (missing 'by_mode' key): %s", path)
        sys.exit(2)
    return data


def load_thresholds(path: Path) -> dict[str, float]:
    """Load per-metric thresholds from a JSON file."""
    if not path.exists():
        logger.error("Thresholds file not found: %s", path)
        sys.exit(2)
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------


def resolve_threshold(
    metric_name: str,
    default_threshold: float,
    per_metric_thresholds: dict[str, float] | None,
    strict: bool,
) -> float:
    """Determine the threshold for a given metric name."""
    if strict:
        return 0.0
    if per_metric_thresholds and metric_name in per_metric_thresholds:
        return per_metric_thresholds[metric_name]
    return default_threshold


def compare_metrics(
    baseline: dict[str, Any],
    current: dict[str, Any],
    default_threshold: float,
    per_metric_thresholds: dict[str, float] | None,
    strict: bool,
) -> list[MetricComparison]:
    """Compare all (mode, difficulty, metric) triples present in both files."""
    results: list[MetricComparison] = []

    baseline_modes = baseline.get("by_mode", {})
    current_modes = current.get("by_mode", {})

    for mode in sorted(set(baseline_modes) & set(current_modes)):
        baseline_diffs = baseline_modes[mode]
        current_diffs = current_modes[mode]

        for difficulty in sorted(set(baseline_diffs) & set(current_diffs)):
            baseline_metrics = baseline_diffs[difficulty]
            current_metrics = current_diffs[difficulty]

            for metric_name in sorted(set(baseline_metrics) & set(current_metrics)):
                if metric_name in SKIP_FIELDS:
                    continue

                b_val = baseline_metrics[metric_name]
                c_val = current_metrics[metric_name]
                delta = c_val - b_val

                threshold = resolve_threshold(
                    metric_name, default_threshold, per_metric_thresholds, strict
                )

                if delta < -threshold:
                    status = "REGRESSED"
                elif delta > threshold:
                    status = "IMPROVED"
                else:
                    status = "OK"

                results.append(
                    MetricComparison(
                        mode=mode,
                        difficulty=difficulty,
                        metric=metric_name,
                        baseline=b_val,
                        current=c_val,
                        delta=delta,
                        threshold=threshold,
                        status=status,
                    )
                )

    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_table(comparisons: list[MetricComparison]) -> str:
    """Format comparisons as a fixed-width text table."""
    headers = ["Mode", "Difficulty", "Metric", "Baseline", "Current", "Delta", "Status"]
    col_widths = [len(h) for h in headers]

    rows: list[list[str]] = []
    for c in comparisons:
        sign = "+" if c.delta >= 0 else ""
        row = [
            c.mode,
            c.difficulty,
            c.metric,
            f"{c.baseline:.3f}",
            f"{c.current:.3f}",
            f"{sign}{c.delta:.3f}",
            c.status,
        ]
        rows.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    lines = [fmt.format(*headers)]
    lines.append("  ".join("-" * w for w in col_widths))
    for row in rows:
        lines.append(fmt.format(*row))

    return "\n".join(lines)


def build_report(
    comparisons: list[MetricComparison],
    baseline_path: str,
    current_path: str,
    default_threshold: float,
) -> ComparisonReport:
    """Build a structured comparison report from metric comparisons."""
    report = ComparisonReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        baseline_path=baseline_path,
        current_path=current_path,
        threshold=default_threshold,
    )

    for c in comparisons:
        entry = {
            "mode": c.mode,
            "difficulty": c.difficulty,
            "metric": c.metric,
            "baseline": c.baseline,
            "current": c.current,
            "delta": c.delta,
            "threshold": c.threshold,
        }
        if c.status == "REGRESSED":
            report.regressions.append(entry)
        elif c.status == "IMPROVED":
            report.improvements.append(entry)
        else:
            report.unchanged.append(entry)

    report.passed = len(report.regressions) == 0
    return report


def write_report(report: ComparisonReport, path: Path) -> None:
    """Serialize the comparison report to a JSON file."""
    data = {
        "timestamp": report.timestamp,
        "baseline_path": report.baseline_path,
        "current_path": report.current_path,
        "threshold": report.threshold,
        "regressions": report.regressions,
        "improvements": report.improvements,
        "unchanged": report.unchanged,
        "passed": report.passed,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Comparison report written to %s", path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the comparison CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Compare experiment metrics against a baseline. "
            "Exits 0 if no regressions, 1 if regressions found, 2 on input errors."
        ),
    )
    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Path to the current experiment's metrics.json.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to the baseline metrics.json.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Default regression threshold (drop must exceed this to count). Default: 0.05.",
    )
    parser.add_argument(
        "--thresholds-file",
        type=Path,
        default=None,
        help="JSON file with per-metric thresholds. Overrides --threshold for listed metrics.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: any decrease at all is treated as a regression (threshold=0).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write a comparison.json report.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )
    return parser


def main() -> None:
    """Entry point for the baseline comparison CLI."""
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(level="DEBUG" if args.verbose else "INFO")

    logger.info("Loading baseline: %s", args.baseline)
    baseline = load_metrics(args.baseline)

    logger.info("Loading current: %s", args.current)
    current = load_metrics(args.current)

    per_metric_thresholds: dict[str, float] | None = None
    if args.thresholds_file:
        logger.info("Loading per-metric thresholds: %s", args.thresholds_file)
        per_metric_thresholds = load_thresholds(args.thresholds_file)

    comparisons = compare_metrics(
        baseline=baseline,
        current=current,
        default_threshold=args.threshold,
        per_metric_thresholds=per_metric_thresholds,
        strict=args.strict,
    )

    if not comparisons:
        print("No overlapping metrics found between baseline and current.")
        sys.exit(0)

    print(format_table(comparisons))
    print()

    report = build_report(
        comparisons=comparisons,
        baseline_path=str(args.baseline.resolve()),
        current_path=str(args.current.resolve()),
        default_threshold=args.threshold,
    )

    regression_count = len(report.regressions)
    improvement_count = len(report.improvements)

    print(
        f"Summary: {regression_count} regression(s), "
        f"{improvement_count} improvement(s), "
        f"{len(report.unchanged)} unchanged."
    )

    if args.output:
        write_report(report, args.output)

    if not report.passed:
        logger.warning("Regressions detected -- failing gate.")
        sys.exit(1)
    else:
        logger.info("All metrics within threshold -- gate passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
