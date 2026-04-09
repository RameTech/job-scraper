"""Job scraper pipeline: scrape → filter → score → store → report."""
from __future__ import annotations

import argparse
import asyncio
from dotenv import load_dotenv  # type: ignore[import]

from config_schema import load_config
from scraper import create_browser_context, run_scrapers
from analyzer import filter_listings, rank_listings
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
    ranked = rank_listings(listings, config)

    new_count = 0
    for listing, score in ranked:
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
            "score": score,
        }
        if not dry_run:
            _, is_new = upsert_listing(data)
            if is_new:
                new_count += 1
                tag = _score_tag(score)
                print(f"[NEW] [{tag}] {listing.title} @ {listing.company}  score={score}")

    print(f"\nDone. {len(ranked)} listings passed filters, {new_count} new.")


def _score_tag(score: int) -> str:
    if score >= 80:
        return "★★★"
    if score >= 50:
        return "★★ "
    if score >= 20:
        return "★  "
    return "   "


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job scraper")
    parser.add_argument("--source", choices=["linkedin", "indeed"], help="Scrape only this source")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = parser.parse_args()

    asyncio.run(main(source_override=args.source, dry_run=args.dry_run))
