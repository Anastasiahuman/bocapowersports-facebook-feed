#!/usr/bin/env python3
"""
Build a Facebook Commerce Manager compatible feed CSV from scraped listings.

Input priority:
1) output/raw_listings.json
2) output/raw_listings.csv

Output:
- output/facebook_feed.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any

RAW_JSON = Path("output/raw_listings.json")
RAW_CSV = Path("output/raw_listings.csv")
OUTPUT_CSV = Path("output/facebook_feed.csv")
DEFAULT_CURRENCY = "USD"
DEFAULT_DESCRIPTION_MAX_LEN = 5000

# -----------------------------
# Pricing config (easy to edit)
# -----------------------------
# final_price = original_price + PRICE_ADJUSTMENT
PRICE_ADJUSTMENT = 100


def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def clean_text(value: Any) -> str:
    """Convert any value to clean string, keep blank for missing."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("&quot;", '"').replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_condition(value: Any) -> str:
    """
    Facebook condition fallback:
    - keep new/used/refurbished if clear
    - default to used
    """
    raw = clean_text(value).lower()
    if raw in {"new", "used", "refurbished"}:
        return raw
    if "new" in raw:
        return "new"
    if "refurb" in raw:
        return "refurbished"
    if "use" in raw:
        return "used"
    return "used"


def parse_original_price(value: Any) -> float | None:
    """Parse original website price into a numeric value."""
    raw = clean_text(value)
    if not raw:
        return None

    # Keep first number from strings like "$15,999.00" or "15999"
    match = re.search(r"\d+(?:[.,]\d+)?", raw.replace(",", ""))
    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def apply_pricing_rule(original_price: float | None) -> float | None:
    """Apply configurable pricing rule."""
    if original_price is None:
        return None
    return original_price + PRICE_ADJUSTMENT


def format_facebook_price(value: float | None, currency: str) -> str:
    """Format price for Facebook feed: 15999 USD."""
    if value is None:
        return ""
    # Keep integer style for cleaner feed values.
    if float(value).is_integer():
        return f"{int(value)} {currency}"
    return f"{value:.2f} {currency}"


def clean_description(value: Any, max_len: int = DEFAULT_DESCRIPTION_MAX_LEN) -> str:
    """
    Remove common scraper noise from description while keeping useful text.
    """
    text = clean_text(value)
    if not text:
        return ""

    # Remove VIN-like tokens (11-20 alphanumeric uppercase chars).
    text = re.sub(r"\b[A-Z0-9]{11,20}\b", " ", text)

    # Remove glued machine-like chunks (typical VIN/mileage/noise without spaces).
    text = re.sub(r"\b[A-Z]{2,}[A-Z0-9,./-]{8,}\b", " ", text)
    text = re.sub(r"\b\d{2,},\d{3}[A-Za-z0-9,./-]*\b", " ", text)

    # Remove mileage fragments like "18,374 mi" / "140,212mi".
    text = re.sub(r"\b\d{1,3}(?:,\d{3})+\s*mi\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+\s*mi\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+\s*mi[A-Za-z0-9./-]*\b", " ", text, flags=re.IGNORECASE)

    # Remove long merged alphanumeric blobs often caused by bad spacing.
    text = re.sub(r"\b[A-Za-z]{3,}\d{3,}[A-Za-z0-9,./-]*\b", " ", text)

    # Collapse repeated punctuation and spaces.
    text = re.sub(r"[|]{2,}", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.;")

    # Keep CSV clean and practical.
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "..."

    return text


def build_fallback_description(raw: dict[str, Any]) -> str:
    """
    Build a minimal readable description when source description is missing.
    """
    title = clean_text(raw.get("title"))
    year = clean_text(raw.get("year"))
    brand = clean_text(raw.get("brand_or_make"))
    model = clean_text(raw.get("model"))
    price = clean_text(raw.get("price"))

    header = title or "Pre-owned boat available"
    spec_line_parts = [p for p in [year, brand, model] if p]
    spec_line = " ".join(spec_line_parts).strip()

    sentences: list[str] = [header]
    if spec_line:
        sentences.append(f"Clean and well-kept {spec_line}.")
    else:
        sentences.append("Clean and well-kept pre-owned boat.")

    if price:
        sentences.append(f"Priced at ${price}.")

    sentences.append("Ready for the water.")
    sentences.append("Message us for full specs, walkaround photos, and availability.")
    return " ".join(sentences)


def load_raw_data(json_path: Path, csv_path: Path) -> list[dict[str, Any]]:
    """Load scraped listings from JSON first, fallback to CSV."""
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]

    if csv_path.exists():
        rows: list[dict[str, Any]] = []
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        return rows

    return []


def map_row(raw: dict[str, Any], currency: str) -> dict[str, str]:
    """Map raw scraped listing into Facebook feed columns."""
    description = clean_description(raw.get("description"))
    if not description:
        description = build_fallback_description(raw)

    original_price = parse_original_price(raw.get("price"))
    final_price = apply_pricing_rule(original_price)

    logging.info(
        "Pricing | id=%s | original=%s | final=%s",
        clean_text(raw.get("id")),
        original_price if original_price is not None else "N/A",
        final_price if final_price is not None else "N/A",
    )

    return {
        "id": clean_text(raw.get("id")),
        "title": clean_text(raw.get("title")),
        "description": description,
        "availability": "in stock",
        "condition": normalize_condition(raw.get("condition")),
        "price": format_facebook_price(final_price, currency),
        "link": clean_text(raw.get("listing_url")),
        "image_link": clean_text(raw.get("main_image_url")),
        "brand": clean_text(raw.get("brand_or_make")),
        "model": clean_text(raw.get("model")),
        "year": clean_text(raw.get("year")),
        "category": clean_text(raw.get("category")),
    }


def is_boat_listing(row: dict[str, str]) -> bool:
    """Keep only boat listings based on title and description keywords."""
    text = f"{row.get('title', '')} {row.get('description', '')}".lower()
    boat_keywords = [
        "boat",
        "fishing",
        "sundeck",
        "sportfish",
        "caddy cabin",
        "wellcraft",
        "hydra",
        "robalo",
        "triton",
        "hurricane",
        "glacier bay",
        "mako",
    ]
    return any(keyword in text for keyword in boat_keywords)


def write_feed(path: Path, rows: list[dict[str, str]]) -> None:
    """Write mapped rows to output/facebook_feed.csv."""
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
        "brand",
        "model",
        "year",
        "category",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Facebook Commerce feed CSV from scraped data.")
    parser.add_argument("--json-input", type=Path, default=RAW_JSON, help="Path to raw_listings.json")
    parser.add_argument("--csv-input", type=Path, default=RAW_CSV, help="Path to raw_listings.csv fallback")
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV, help="Path to output facebook_feed.csv")
    parser.add_argument("--currency", default=DEFAULT_CURRENCY, help="Currency code, default: USD")
    parser.add_argument(
        "--description-max-len",
        type=int,
        default=DEFAULT_DESCRIPTION_MAX_LEN,
        help="Maximum description length after cleaning.",
    )
    args = parser.parse_args()

    setup_logger()
    raw_rows = load_raw_data(args.json_input, args.csv_input)
    if not raw_rows:
        logging.error("No input data found. Expected %s or %s", args.json_input, args.csv_input)
        raise SystemExit(1)

    mapped: list[dict[str, str]] = []
    for row in raw_rows:
        mapped_row = map_row(row, args.currency)
        mapped_row["description"] = clean_description(
            mapped_row.get("description", ""),
            max_len=max(args.description_max_len, 100),
        )
        mapped.append(mapped_row)

    # Keep rows even if some fields are missing, but require minimal id/title/link
    exported = [row for row in mapped if row.get("id") and row.get("title") and row.get("link")]

    # Keep only boats and force correct final category value.
    exported = [row for row in exported if is_boat_listing(row)]
    for row in exported:
        row["category"] = "boat"

    write_feed(args.output, exported)
    logging.info("Feed written to: %s", args.output)
    logging.info("Exported listings: %d", len(exported))


if __name__ == "__main__":
    main()
