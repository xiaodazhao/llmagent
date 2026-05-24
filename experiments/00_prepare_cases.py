"""Generate a draft experiment case list."""

from __future__ import annotations

import argparse
from pathlib import Path

from common import CASES_DIR, available_dates, draft_cases_from_dates, ensure_experiment_dirs, write_case_csv


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Prepare a draft case list for experiments.")
    parser.add_argument(
        "--output",
        type=Path,
        default=CASES_DIR / "case_list.csv",
        help="Output CSV path for the experiment case list.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Maximum number of draft cases to generate from available dates.",
    )
    parser.add_argument(
        "--dates",
        nargs="*",
        default=None,
        help="Optional explicit date list in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def main() -> None:
    """Create the draft case CSV."""
    args = parse_args()
    ensure_experiment_dirs()
    dates = args.dates or available_dates(limit=args.limit)
    rows = draft_cases_from_dates(dates)
    write_case_csv(args.output, rows)
    print(f"Wrote {len(rows)} draft cases to {args.output}")


if __name__ == "__main__":
    main()
