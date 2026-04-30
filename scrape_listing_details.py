#!/usr/bin/env python3
"""
Step 2 scraper:
- Read listing URLs collected by scrape_inventory.py
- Scrape product detail pages
- Save raw JSON + CSV for Facebook feed mapping
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

INPUT_URLS_PATH = Path("output/listing_urls.json")
OUTPUT_JSON_PATH = Path("output/raw_listings.json")
OUTPUT_CSV_PATH = Path("output/raw_listings.csv")


def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def extract_structured_product(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.select('script[type="application/ld+json"]')
    for script in scripts:
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict) and payload.get("@type") == "Product":
            return payload
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    return item

    return {}


def first_price(product: dict[str, Any]) -> str:
    offers = product.get("Offers") or product.get("offers") or {}
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if isinstance(offers, dict):
        value = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")
        if value is not None:
            return str(value)
    return ""


def extract_image_urls(product: dict[str, Any]) -> tuple[str, list[str]]:
    image_data = product.get("image", [])
    images: list[str] = []

    if isinstance(image_data, str):
        images = [image_data]
    elif isinstance(image_data, list):
        for item in image_data:
            if isinstance(item, str):
                images.append(item)
            elif isinstance(item, dict):
                content_url = item.get("contentUrl") or item.get("url")
                if content_url:
                    images.append(content_url)

    # Preserve order while removing duplicates
    deduped: list[str] = []
    seen: set[str] = set()
    for img in images:
        if img in seen:
            continue
        seen.add(img)
        deduped.append(img)

    main = deduped[0] if deduped else ""
    additional = deduped[1:] if len(deduped) > 1 else []
    return main, additional


def extract_wix_image_urls_from_html(html: str) -> list[str]:
    # Grab original image asset URLs directly from page source.
    matches = re.findall(r"https://static\\.wixstatic\\.com/media/[^\"'\\s)]+", html)
    cleaned: list[str] = []
    for url in matches:
        # Remove escaped slashes and trim common wix transform suffixes if present.
        candidate = url.replace("\\/", "/")
        cleaned.append(candidate)

    deduped: list[str] = []
    seen: set[str] = set()
    for url in cleaned:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def filter_working_images(urls: list[str]) -> list[str]:
    working: list[str] = []
    for url in urls:
        try:
            resp = requests.get(url, timeout=20)
            content_type = resp.headers.get("content-type", "").lower()
            if resp.status_code == 200 and "image" in content_type:
                working.append(url)
        except requests.RequestException:
            continue
    return working


def infer_fields(title: str, description: str, url: str) -> dict[str, str]:
    text = f"{title} {description}".strip()
    words = [w for w in re.split(r"\s+", title.strip()) if w]

    year_match = re.search(r"\b(19|20)\d{2}\b", title)
    year = year_match.group(0) if year_match else ""

    brand = words[1] if len(words) > 1 and year else (words[0] if words else "")
    model = " ".join(words[2:5]) if year and len(words) > 2 else (" ".join(words[1:4]) if len(words) > 1 else "")

    condition = ""
    if re.search(r"\bused\b", text, flags=re.IGNORECASE):
        condition = "used"
    elif re.search(r"\bnew\b", text, flags=re.IGNORECASE):
        condition = "new"

    category = ""
    title_l = title.lower()
    if any(k in title_l for k in ["boat", "deck", "fishing", "caddy"]):
        category = "boat"
    elif any(k in title_l for k in ["truck", "van", "ford f-59", "sprinter"]):
        category = "truck/van"
    elif any(k in title_l for k in ["trailer"]):
        category = "trailer"
    elif any(k in title_l for k in ["jeep", "mini cooper", "tesla", "corvette", "bmw", "nissan", "chevrolet"]):
        category = "car"
    else:
        category = "motorcycle/powersports"

    listing_id = urlparse(url).path.rstrip("/").split("/")[-1]

    return {
        "id": listing_id,
        "brand_or_make": brand,
        "model": model,
        "year": year,
        "condition": condition,
        "category": category,
    }


def parse_listing(url: str) -> dict[str, Any]:
    logging.info("Scraping listing: %s", url)
    result: dict[str, Any] = {
        "id": "",
        "title": "",
        "price": "",
        "description": "",
        "listing_url": url,
        "main_image_url": "",
        "additional_image_urls": [],
        "brand_or_make": "",
        "model": "",
        "year": "",
        "condition": "",
        "category": "",
    }
    try:
        html = fetch_html(url)
        product = extract_structured_product(html)

        title = (product.get("name") or "").strip() if isinstance(product, dict) else ""
        description = (product.get("description") or "").strip() if isinstance(product, dict) else ""
        price = first_price(product) if isinstance(product, dict) else ""
        main_image_url, additional_image_urls = extract_image_urls(product) if isinstance(product, dict) else ("", [])
        html_images = extract_wix_image_urls_from_html(html)

        all_images: list[str] = []
        if main_image_url:
            all_images.append(main_image_url)
        all_images.extend(additional_image_urls)
        all_images.extend(html_images)

        # Deduplicate and keep only working image URLs.
        deduped_images: list[str] = []
        seen: set[str] = set()
        for image_url in all_images:
            if image_url in seen:
                continue
            seen.add(image_url)
            deduped_images.append(image_url)
        working_images = filter_working_images(deduped_images)

        main_image_url = working_images[0] if working_images else ""
        additional_image_urls = working_images[1:] if len(working_images) > 1 else []

        inferred = infer_fields(title, description, url)
        result.update(
            {
                "id": inferred["id"],
                "title": title,
                "price": price,
                "description": description,
                "main_image_url": main_image_url,
                "additional_image_urls": additional_image_urls,
                "brand_or_make": inferred["brand_or_make"],
                "model": inferred["model"],
                "year": inferred["year"],
                "condition": inferred["condition"],
                "category": inferred["category"],
            }
        )
    except requests.RequestException as exc:
        logging.error("Request failed for %s: %s", url, exc)
    except Exception as exc:  # noqa: BLE001
        logging.error("Unexpected parsing error for %s: %s", url, exc)

    return result


def load_urls(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    urls = payload.get("urls", [])
    return [u for u in urls if isinstance(u, str) and u.strip()]


def write_json(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.info("Saved JSON: %s", path)


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "title",
        "price",
        "description",
        "listing_url",
        "main_image_url",
        "additional_image_urls",
        "brand_or_make",
        "model",
        "year",
        "condition",
        "category",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row_for_csv = dict(row)
            row_for_csv["additional_image_urls"] = "|".join(row.get("additional_image_urls", []))
            writer.writerow(row_for_csv)
    logging.info("Saved CSV: %s", path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape listing details from listing URLs.")
    parser.add_argument("--input", type=Path, default=INPUT_URLS_PATH, help="Path to listing URL JSON file.")
    parser.add_argument("--json-output", type=Path, default=OUTPUT_JSON_PATH, help="Raw JSON output path.")
    parser.add_argument("--csv-output", type=Path, default=OUTPUT_CSV_PATH, help="Raw CSV output path.")
    args = parser.parse_args()

    setup_logger()
    if not args.input.exists():
        logging.error("Input file not found: %s", args.input)
        raise SystemExit(1)

    urls = load_urls(args.input)
    if not urls:
        logging.error("No listing URLs found in: %s", args.input)
        raise SystemExit(1)

    listings = [parse_listing(url) for url in urls]
    write_json(listings, args.json_output)
    write_csv(listings, args.csv_output)
    logging.info("Done. Scraped %d listings.", len(listings))


if __name__ == "__main__":
    main()
