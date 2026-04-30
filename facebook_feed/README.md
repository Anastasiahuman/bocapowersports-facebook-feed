# Facebook Feed Mapper

Converts `output/raw_listings.json` into a Commerce Manager friendly CSV feed.

## Run

```bash
python facebook_feed/build_facebook_feed.py
```

Optional:

```bash
python facebook_feed/build_facebook_feed.py --currency USD
```

## Input

- `output/raw_listings.json`

## Output

- `output/facebook_feed/facebook_catalog_feed.csv`

## Notes

- Missing fields are left blank when possible.
- Condition is normalized to `new` or `used` (default `used`).
- Price is exported as `number + currency` (example: `16900 USD`).
