#!/usr/bin/env python3
"""
Step 1 scraper:
- Visit inventory page
- Collect listing URLs
- Keep only first N items for MVP test
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.bocapowersports.com"
INVENTORY_URL = f"{BASE_URL}/shop"
DEFAULT_LIMIT = 5
OUTPUT_PATH = Path("output/listing_urls.json")


def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def is_product_link(href: str) -> bool:
    if not href:
        return False
    path = urlparse(href).path
    return "/product-page/" in path


def fetch_inventory_html(url: str) -> str:
    logging.info("Fetching inventory page: %s", url)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def extract_listing_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()

    for link in soup.select("a[href]"):
        href = link.get("href", "").strip()
        full_url = urljoin(BASE_URL, href)
        if not is_product_link(full_url):
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        urls.append(full_url)

    return urls


def save_urls(urls: list[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": INVENTORY_URL, "count": len(urls), "urls": urls}
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.info("Saved %d URLs to %s", len(urls), output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Find product listing URLs from Boca Power Sports.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="How many listing URLs to keep.")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Where to save listing URLs as JSON.",
    )
    args = parser.parse_args()

    setup_logger()
    try:
        html = fetch_inventory_html(INVENTORY_URL)
        urls = extract_listing_urls(html)
        if not urls:
            logging.warning("No listing URLs found. Site markup may have changed.")
            save_urls([], args.output)
            return

        limited = urls[: max(args.limit, 1)]
        logging.info("Found %d total listing URLs, taking %d", len(urls), len(limited))
        save_urls(limited, args.output)
    except requests.RequestException as exc:
        logging.error("Network error while fetching inventory: %s", exc)
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        logging.error("Unexpected error: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
