"""Job scraper pipeline: scrape → filter → store → report."""
from __future__ import annotations

import argparse
import asyncio
from dotenv import load_dotenv  # type: ignore[import]

from config_schema import load_config
from scraper import create_browser_context, run_scrapers
from analyzer import filter_listings
from store import init_db, upsert_listing


async def main(source_override: str | None = None, dry_run: bool = False) -> None:
    load_dotenv()
    config = load_config()

    if source_override:
        config.search.sources = [source_override]

    init_db(config.storage.db_path)

    pw, browser, context = await create_browser_context(headless=config.scraper.headless)
    try:
        listings = await run_scrapers(config, context)
    finally:
        await context.close()
        await browser.close()
        await pw.stop()

    listings = filter_listings(listings, config)

    new_count = 0
    for listing in listings:
        data = {
            "source": listing.source,
            "external_id": listing.external_id,
            "title": listing.title,
            "company": listing.company,
            "location": listing.location,
            "url": listing.url,
            "description": listing.description,
            "salary": listing.salary,
            "posted_at": listing.posted_at,
        }
        if not dry_run:
            _, is_new = upsert_listing(data)
            if is_new:
                new_count += 1
                print(f"[NEW] {listing.title} @ {listing.company} ({listing.source})")

    print(f"\nDone. {len(listings)} listings found, {new_count} new.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job scraper")
    parser.add_argument("--source", choices=["linkedin", "indeed"], help="Scrape only this source")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = parser.parse_args()

    asyncio.run(main(source_override=args.source, dry_run=args.dry_run))
