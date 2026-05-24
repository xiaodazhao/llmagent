"""Create an ablation plan for CST-LLM experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from common import CASES_DIR, METRICS_DIR, ensure_experiment_dirs, load_case_csv, write_rows_csv


ABLATION_VARIANTS = [
    ("full", "Full CST-LLM", "Complete method with full CST, indicators, and prompt constraints."),
    ("wo_geo", "w/o Geo", "Remove geological evidence state and keep operation-side state only."),
    (
        "wo_alignment",
        "w/o Spatial Alignment",
        "Keep PLC and geology summaries but remove explicit chainage-level alignment.",
    ),
    (
        "wo_constraints",
        "w/o Prompt Constraints",
        "Keep CST but remove cautious wording and evidence boundary constraints.",
    ),
    (
        "wo_indicators",
        "w/o GRS/RAI/GRCI",
        "Keep CST base state but remove indicator-guided attention summarization.",
    ),
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate an ablation study plan.")
    parser.add_argument(
        "--case-list",
        type=Path,
        default=CASES_DIR / "case_list.csv",
        help="CSV file describing experiment cases.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=METRICS_DIR / "ablation_plan.csv",
        help="Path for the ablation plan CSV.",
    )
    return parser.parse_args()


def main() -> None:
    """Write a CSV describing ablation variants for each case."""
    args = parse_args()
    ensure_experiment_dirs()
    cases = load_case_csv(args.case_list)
    rows = []
    for case in cases:
        for variant_id, variant_name, description in ABLATION_VARIANTS:
            rows.append(
                {
                    "case_id": case["case_id"],
                    "date": case["date"],
                    "variant_id": variant_id,
                    "variant_name": variant_name,
                    "description": description,
                }
            )
    write_rows_csv(args.output, rows)
    print(f"Wrote ablation plan: {args.output}")


if __name__ == "__main__":
    main()
