"""Command-line interface for autoPaper.

Examples:
  python -m autopaper.cli --venue HPCA --years 2023 2024 --keywords "prefetch" "GPU"
  python -m autopaper.cli --venue ISCA --years 2024 --keywords "security" --no-download
  python -m autopaper.cli --venue SC --years 2023 --keywords "MPI" --limit 5
"""

from __future__ import annotations

import argparse
import sys

from .config import Config
from .pipeline import run


def _parse_years(tokens: list[str]) -> list[int]:
    years: list[int] = []
    for t in tokens:
        if "-" in t:  # range like 2020-2023
            lo, hi = t.split("-", 1)
            years.extend(range(int(lo), int(hi) + 1))
        else:
            years.append(int(t))
    return sorted(set(years))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="autopaper",
        description="Fetch, download, and digest venue papers via DBLP + Claude Code.",
    )
    ap.add_argument("--venue", required=True,
                    help="Venue acronym, e.g. HPCA, ISCA, SC, ICS, MICRO")
    ap.add_argument("--years", nargs="+", required=True,
                    help="Years or ranges, e.g. 2024 or 2020-2024")
    ap.add_argument("--keywords", nargs="*", default=[],
                    help="Keywords to match in title/abstract (empty = all papers)")
    ap.add_argument("--match", choices=["any", "all"], default="any",
                    help="Require ANY keyword (default) or ALL keywords")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process at most N matched papers")
    ap.add_argument("--no-download", action="store_true",
                    help="Skip PDF downloading (abstracts-only triage)")
    ap.add_argument("--no-summarize", action="store_true",
                    help="Skip Claude summarization")
    ap.add_argument("--config", default=None, help="Path to config.yaml")
    args = ap.parse_args(argv)

    cfg = Config.load(args.config)
    years = _parse_years(args.years)

    matched = run(
        cfg,
        venue=args.venue,
        years=years,
        keywords=args.keywords,
        match_mode=args.match,
        do_download=not args.no_download,
        do_summarize=not args.no_summarize,
        limit=args.limit,
    )

    print(f"\nDone. {len(matched)} matched papers.")
    print(f"  Summaries: {cfg.path('summary_dir')}")
    print(f"  PDFs:      {cfg.path('pdf_dir')}")
    print(f"  Metadata:  {cfg.path('db_path')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
