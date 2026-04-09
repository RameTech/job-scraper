"""Job scraper pipeline: scrape → filter → score → store → report."""
from __future__ import annotations

import argparse
import asyncio
from dotenv import load_dotenv  # type: ignore[import]

from config_schema import load_config
from scraper import create_browser_context, run_scrapers
from analyzer import ScoredListing, filter_listings, rank_listings
from store import init_db, upsert_listing


async def main(
    source_override: str | None = None,
    dry_run: bool = False,
    sort_by: str = "total",
) -> None:
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
    ranked = rank_listings(listings, config, sort_by=sort_by)

    new_count = 0
    _print_header(sort_by)

    for sl in ranked:
        data = {
            "source": sl.listing.source,
            "external_id": sl.listing.external_id,
            "title": sl.listing.title,
            "company": sl.listing.company,
            "location": sl.listing.location,
            "url": sl.listing.url,
            "description": sl.listing.description,
            "salary": sl.listing.salary,
            "posted_at": sl.listing.posted_at,
            "role_score": sl.role_score,
            "visa_score": sl.visa_score,
            "candidate_score": sl.candidate_score,
            "score": sl.total,
        }
        if not dry_run:
            _, is_new = upsert_listing(data)
            if is_new:
                new_count += 1
                _print_listing(sl)

    print(f"\n{'─' * 80}")
    print(f"  {len(ranked)} listings passed filters  |  {new_count} new")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_header(sort_by: str) -> None:
    sort_label = {"total": "total", "role": "role fit", "visa": "visa", "candidate": "candidate fit"}
    print(f"\n{'─' * 80}")
    print(f"  Sorted by: {sort_label.get(sort_by, sort_by)}")
    print(f"  {'ROLE':>4}  {'VISA':>4}  {'CAND':>4}  {'TOT':>4}  TITLE @ COMPANY")
    print(f"{'─' * 80}")


def _print_listing(sl: ScoredListing) -> None:
    stars = _stars(sl.total)
    title = sl.listing.title[:45]
    company = sl.listing.company[:25]
    print(
        f"  {sl.role_score:>4}  {sl.visa_score:>4}  {sl.candidate_score:>4}  "
        f"{sl.total:>4}  {stars} {title} @ {company}"
    )


def _stars(total: int) -> str:
    if total >= 120:
        return "★★★"
    if total >= 70:
        return "★★ "
    if total >= 30:
        return "★  "
    return "   "


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job scraper — London visa-eligible roles")
    parser.add_argument("--source", choices=["linkedin", "indeed"], help="Scrape only this source")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument(
        "--sort-by",
        choices=["total", "role", "visa", "candidate"],
        default="total",
        help="Which score to sort results by (default: total)",
    )
    args = parser.parse_args()

    asyncio.run(main(source_override=args.source, dry_run=args.dry_run, sort_by=args.sort_by))
