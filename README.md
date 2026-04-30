# Boca Power Sports Scraper MVP

Small Python MVP to test scraping listings from `bocapowersports.com` and saving raw data that can later be mapped into a Facebook Commerce Manager feed.

## Why this approach

- The inventory page (`/shop`) exposes direct listing links in static HTML.
- Product pages expose structured data in `application/ld+json` (`@type: Product`), including title, description, price, and images.
- Because of that, `requests + BeautifulSoup` is enough for this MVP (no Playwright needed right now).

## Project structure

- `scrape_inventory.py` - finds product URLs and saves first N (default: 5)
- `scrape_listing_details.py` - scrapes details for saved URLs
- `output/raw_listings.json` - raw listing objects
- `output/raw_listings.csv` - CSV version of raw data
- `requirements.txt` - dependencies

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

### 1) Collect 3-5 listing URLs

```bash
python scrape_inventory.py --limit 5
```

This writes:
- `output/listing_urls.json`

### 2) Scrape listing details

```bash
python scrape_listing_details.py
```

This writes:
- `output/raw_listings.json`
- `output/raw_listings.csv`

### 3) Build Facebook Commerce feed CSV

```bash
python build_facebook_feed.py
```

This writes:
- `output/facebook_feed.csv`

### 4) Run full update pipeline

```bash
python update_feed.py --limit 200 --currency USD
```

This runs all steps in order:
- `scrape_inventory.py`
- `scrape_listing_details.py`
- `build_facebook_feed.py`

It refreshes:
- `output/listing_urls.json`
- `output/raw_listings.json`
- `output/raw_listings.csv`
- `output/facebook_feed.csv`

## Notes

- If a field is missing, script leaves it blank and continues.
- Logs are printed for progress and errors.
- If site markup changes, update selectors and field extraction helpers in scripts.

## Next step toward Facebook feed

Included now:
- `build_facebook_feed.py` maps scraped data into a Commerce Manager compatible CSV with:
  `id`, `title`, `description`, `availability`, `condition`, `price`, `link`, `image_link`, `brand`, `model`, `year`, `category`.

## GitHub automation

Workflow file:
- `.github/workflows/update_feed.yml`

What it does:
- Runs on schedule (daily at `09:00 UTC`) and manual trigger
- Executes `python update_feed.py`
- Commits and pushes updated output files

## Feed URL for Facebook Commerce Manager

After pushing this repo to GitHub, use one of these URLs:

### Option A: Raw GitHub URL (recommended)

```text
https://raw.githubusercontent.com/<your-username>/<your-repo>/<branch>/output/facebook_feed.csv
```

Example with `main` branch:

```text
https://raw.githubusercontent.com/<your-username>/<your-repo>/main/output/facebook_feed.csv
```

### Option B: GitHub Pages URL

Enable GitHub Pages and publish from repository root, then use:

```text
https://<your-username>.github.io/<your-repo>/output/facebook_feed.csv
```
