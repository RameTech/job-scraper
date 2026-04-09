"""Filter and score job listings."""
from __future__ import annotations

from scraper import RawListing
from config_schema import Config, ScoringConfig
from sponsors import is_sponsor
from visa_rules import visa_score as _visa_score


# ---------------------------------------------------------------------------
# Filtering (hard exclusions)
# ---------------------------------------------------------------------------

def _mentions_no_visa(text: str, phrases: list[str]) -> bool:
    """Return True if text contains any phrase signalling no visa sponsorship."""
    lower = text.lower()
    return any(phrase.lower() in lower for phrase in phrases)


def _location_matches(listing_location: str, required: str) -> bool:
    """Return True if the listing location contains the required string."""
    return required.lower() in listing_location.lower()


def passes_filters(listing: RawListing, config: Config) -> bool:
    """Return True if the listing passes all hard filters."""
    # Keyword exclusions on title
    title_lower = listing.title.lower()
    for kw in config.filters.exclude_keywords:
        if kw.lower() in title_lower:
            return False

    # Sponsor register check
    if config.filters.sponsors_only:
        if not is_sponsor(listing.company, config.filters.sponsors_csv):
            return False

    # Location must contain the required city
    if config.filters.require_location:
        if not _location_matches(listing.location, config.filters.require_location):
            return False

    # Drop listings that explicitly say they won't sponsor a visa
    if config.filters.no_visa_phrases:
        searchable = f"{listing.title} {listing.description}"
        if _mentions_no_visa(searchable, config.filters.no_visa_phrases):
            return False

    return True


def filter_listings(listings: list[RawListing], config: Config) -> list[RawListing]:
    return [l for l in listings if passes_filters(l, config)]


# ---------------------------------------------------------------------------
# Scoring (soft ranking — higher = better fit)
# ---------------------------------------------------------------------------

def score_listing(listing: RawListing, scoring: ScoringConfig) -> int:
    """
    Return a total relevance score for the listing.

    Breakdown:
        +role_score          title/description matches a target role keyword
        +level_score         entry-level / graduate signal
        +language_score      German speaker / required
        visa sub-score       SOC eligibility + salary vs UK thresholds (see visa_rules.py)
    """
    searchable = f"{listing.title} {listing.description}".lower()
    score = 0

    if any(kw.lower() in searchable for kw in scoring.role_keywords):
        score += scoring.role_score

    if any(kw.lower() in searchable for kw in scoring.level_keywords):
        score += scoring.level_score

    if any(kw.lower() in searchable for kw in scoring.language_keywords):
        score += scoring.language_score

    v = scoring.visa
    visa_breakdown = _visa_score(
        f"{listing.title} {listing.description}",
        eligible_role_score=v.eligible_role_score,
        salary_standard_score=v.salary_standard_score,
        salary_new_entrant_score=v.salary_new_entrant_score,
        salary_below_floor_penalty=v.salary_below_floor_penalty,
        ineligible_role_penalty=v.ineligible_role_penalty,
    )
    score += visa_breakdown.score

    return score


def rank_listings(listings: list[RawListing], config: Config) -> list[tuple[RawListing, int]]:
    """Return listings paired with their score, sorted best-first."""
    scored = [(l, score_listing(l, config.scoring)) for l in listings]
    return sorted(scored, key=lambda x: x[1], reverse=True)
