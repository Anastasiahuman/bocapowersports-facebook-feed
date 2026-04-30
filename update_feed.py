#!/usr/bin/env python3
"""
One-command feed updater for local runs and GitHub Actions.

Pipeline:
1) Collect inventory URLs
2) Scrape listing details
3) Build facebook_feed.csv (boats only)
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path


def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def run_step(command: list[str], cwd: Path) -> None:
    logging.info("Running: %s", " ".join(command))
    subprocess.run(command, cwd=str(cwd), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update facebook feed CSV end-to-end.")
    parser.add_argument("--limit", type=int, default=200, help="Max listing URLs to pull from inventory.")
    parser.add_argument("--currency", default="USD", help="Currency code for output prices.")
    args = parser.parse_args()

    setup_logger()
    root = Path(__file__).resolve().parent

    try:
        run_step([sys.executable, "scrape_inventory.py", "--limit", str(max(args.limit, 1))], cwd=root)
        run_step([sys.executable, "scrape_listing_details.py"], cwd=root)
        run_step([sys.executable, "build_facebook_feed.py", "--currency", args.currency], cwd=root)
        logging.info("Feed update completed: output/facebook_feed.csv")
    except subprocess.CalledProcessError as exc:
        logging.error("Step failed with exit code %s", exc.returncode)
        raise SystemExit(exc.returncode) from exc


if __name__ == "__main__":
    main()
