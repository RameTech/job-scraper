"""Filter and score job listings."""
from __future__ import annotations

from scraper import RawListing
from config_schema import Config


def passes_filters(listing: RawListing, config: Config) -> bool:
    """Return True if the listing should be kept."""
    title_lower = listing.title.lower()
    for kw in config.filters.exclude_keywords:
        if kw.lower() in title_lower:
            return False
    return True


def filter_listings(listings: list[RawListing], config: Config) -> list[RawListing]:
    return [l for l in listings if passes_filters(l, config)]
