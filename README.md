# job-scraper

Scrapes job listings from LinkedIn and Indeed, stores them in SQLite, and surfaces new matches.

## Stack

- **Python 3.12+**
- **Scraping:** Playwright (CDP via patchright)
- **DB:** SQLite via peewee ORM
- **Config:** `config.toml` + `.env` (credentials)
- **Tests:** pytest

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # fill in credentials if needed
```

### Visa sponsor filter (optional)

Download the UK Home Office register of licensed sponsors and place it at `data/sponsors.csv`:

> https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers

Then set `sponsors_only = true` in `config.toml` to filter results to visa-sponsoring companies only.

```bash
python main.py
```

## Structure

```
main.py          # Pipeline entry point: scrape → store → filter → output
scraper.py       # LinkedIn + Indeed scrapers
store.py         # peewee ORM, init_db, upsert_listing
analyzer.py      # Dedup, scoring, filtering
config_schema.py # Pydantic config model
data/            # SQLite DB lives here
tests/           # pytest tests
scripts/         # Utility scripts
```

## Usage

```bash
python main.py                  # Run full pipeline
python main.py --dry-run        # Scrape without storing
python main.py --source linkedin # Only scrape LinkedIn
python main.py --source indeed   # Only scrape Indeed
```
