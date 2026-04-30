#!/usr/bin/env python3
"""
Convert raw scraped listings into a Facebook Commerce Manager feed CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any

INPUT_JSON = Path("output/raw_listings.json")
OUTPUT_CSV = Path("output/facebook_feed/facebook_catalog_feed.csv")
DEFAULT_CURRENCY = "USD"


def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def load_raw_listings(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of listings.")
    return [row for row in data if isinstance(row, dict)]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    # Remove simple HTML entities and collapse spaces
    text = text.replace("&quot;", '"').replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_condition(value: str) -> str:
    raw = normalize_text(value).lower()
    if raw in {"new", "used", "refurbished"}:
        return raw
    if "new" in raw:
        return "new"
    if "use" in raw:
        return "used"
    return "used"


def normalize_price(value: Any, currency: str) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    # Keep first numeric value
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        return ""
    number = match.group(0).replace(",", ".")
    return f"{number} {currency}"


def build_feed_row(raw: dict[str, Any], currency: str) -> dict[str, str]:
    additional = raw.get("additional_image_urls") or []
    if not isinstance(additional, list):
        additional = []

    return {
        "id": normalize_text(raw.get("id")),
        "title": normalize_text(raw.get("title")),
        "description": normalize_text(raw.get("description")),
        "availability": "in stock",
        "condition": normalize_condition(normalize_text(raw.get("condition"))),
        "price": normalize_price(raw.get("price"), currency),
        "link": normalize_text(raw.get("listing_url")),
        "image_link": normalize_text(raw.get("main_image_url")),
        "additional_image_link": ",".join(normalize_text(u) for u in additional if normalize_text(u)),
        "brand": normalize_text(raw.get("brand_or_make")),
        "model": normalize_text(raw.get("model")),
        "year": normalize_text(raw.get("year")),
        "product_type": normalize_text(raw.get("category")),
    }


def write_feed_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "id",
        "title",
        "description",
        "availability",
        "condition",
        "price",
        "link",
        "image_link",
        "additional_image_link",
        "brand",
        "model",
        "year",
        "product_type",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Facebook Commerce feed CSV from raw scraped data.")
    parser.add_argument("--input", type=Path, default=INPUT_JSON, help="Path to raw_listings.json")
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV, help="Path to output feed CSV")
    parser.add_argument("--currency", default=DEFAULT_CURRENCY, help="Price currency code, e.g. USD")
    args = parser.parse_args()

    setup_logger()

    if not args.input.exists():
        logging.error("Input file not found: %s", args.input)
        raise SystemExit(1)

    raw_listings = load_raw_listings(args.input)
    if not raw_listings:
        logging.error("No raw listings found in %s", args.input)
        raise SystemExit(1)

    rows = [build_feed_row(item, args.currency) for item in raw_listings]
    rows = [r for r in rows if r.get("id") and r.get("title") and r.get("link")]
    if not rows:
        logging.error("No valid feed rows after mapping.")
        raise SystemExit(1)

    write_feed_csv(rows, args.output)
    logging.info("Feed created: %s", args.output)
    logging.info("Rows exported: %d", len(rows))


if __name__ == "__main__":
    main()
