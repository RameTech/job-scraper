"""Filter and score job listings across three independent dimensions."""
from __future__ import annotations

from dataclasses import dataclass

from scraper import RawListing
from config_schema import Config, RoleFitConfig, CandidateFitConfig, VisaScoringConfig
from sponsors import is_sponsor
from visa_rules import visa_score as _visa_score


# ---------------------------------------------------------------------------
# Scored listing — carries all three sub-scores plus the total
# ---------------------------------------------------------------------------

@dataclass
class ScoredListing:
    listing: RawListing
    role_score: int       # Score 1: is this the role type we want?
    visa_score: int       # Score 2: can this job be visa-sponsored?
    candidate_score: int  # Score 3: how well does Martha's profile fit?

    @property
    def total(self) -> int:
        return self.role_score + self.visa_score + self.candidate_score


# ---------------------------------------------------------------------------
# Hard filters
# ---------------------------------------------------------------------------

def _mentions_no_visa(text: str, phrases: list[str]) -> bool:
    lower = text.lower()
    return any(phrase.lower() in lower for phrase in phrases)


def passes_filters(listing: RawListing, config: Config) -> bool:
    title_lower = listing.title.lower()
    for kw in config.filters.exclude_keywords:
        if kw.lower() in title_lower:
            return False

    if config.filters.sponsors_only:
        if not is_sponsor(listing.company, config.filters.sponsors_csv):
            return False

    if config.filters.require_location:
        if config.filters.require_location.lower() not in listing.location.lower():
            return False

    if config.filters.no_visa_phrases:
        if _mentions_no_visa(f"{listing.title} {listing.description}", config.filters.no_visa_phrases):
            return False

    return True


def filter_listings(listings: list[RawListing], config: Config) -> list[RawListing]:
    return [l for l in listings if passes_filters(l, config)]


# ---------------------------------------------------------------------------
# Score 1 — Role Fit
# "Is this job posting the kind of role we are targeting?"
# ---------------------------------------------------------------------------

def role_fit_score(listing: RawListing, cfg: RoleFitConfig) -> int:
    """
    Points:
        +role_score      title/description matches a target role keyword
        +level_score     entry-level / graduate signal
        +language_score  German speaker / required (rare requirement → less competition)
    """
    searchable = f"{listing.title} {listing.description}".lower()
    score = 0

    if any(kw.lower() in searchable for kw in cfg.role_keywords):
        score += cfg.role_score

    if any(kw.lower() in searchable for kw in cfg.level_keywords):
        score += cfg.level_score

    if any(kw.lower() in searchable for kw in cfg.language_keywords):
        score += cfg.language_score

    return score


# ---------------------------------------------------------------------------
# Score 2 — Visa Eligibility
# "Can this specific job be sponsored under the Skilled Worker visa?"
# ---------------------------------------------------------------------------

def visa_eligibility_score(listing: RawListing, cfg: VisaScoringConfig) -> int:
    breakdown = _visa_score(
        f"{listing.title} {listing.description}",
        eligible_role_score=cfg.eligible_role_score,
        other_eligible_score=cfg.other_eligible_score,
        salary_standard_score=cfg.salary_standard_score,
        salary_new_entrant_score=cfg.salary_new_entrant_score,
        salary_below_floor_penalty=cfg.salary_below_floor_penalty,
        ineligible_role_penalty=cfg.ineligible_role_penalty,
    )
    return breakdown.score


# ---------------------------------------------------------------------------
# Score 3 — Candidate Fit
# "How competitive is the candidate's profile for this specific job?"
# ---------------------------------------------------------------------------

def candidate_fit_score(listing: RawListing, cfg: CandidateFitConfig) -> int:
    """
    Scores how well the candidate's background matches job requirements.
    Positive signals: matching skills/sector/tools found in the job posting.
    Negative signals: seniority/experience requirements beyond the candidate's level.
    """
    searchable = f"{listing.title} {listing.description}".lower()
    score = 0

    if any(kw.lower() in searchable for kw in cfg.crm_keywords):
        score += cfg.crm_score

    if any(kw.lower() in searchable for kw in cfg.client_relations_keywords):
        score += cfg.client_relations_score

    if any(kw.lower() in searchable for kw in cfg.admin_coord_keywords):
        score += cfg.admin_coord_score

    if any(kw.lower() in searchable for kw in cfg.sector_keywords):
        score += cfg.sector_score

    if any(kw.lower() in searchable for kw in cfg.data_reporting_keywords):
        score += cfg.data_reporting_score

    if any(kw.lower() in searchable for kw in cfg.degree_relevance_keywords):
        score += cfg.degree_relevance_score

    if any(kw.lower() in searchable for kw in cfg.overqualified_keywords):
        score += cfg.overqualified_penalty

    if any(kw.lower() in searchable for kw in cfg.team_management_keywords):
        score += cfg.team_management_penalty

    if any(kw.lower() in searchable for kw in cfg.short_term_keywords):
        score += cfg.short_term_penalty

    return score


# ---------------------------------------------------------------------------
# Combined scoring + ranking
# ---------------------------------------------------------------------------

def score_listing(listing: RawListing, config: Config) -> ScoredListing:
    return ScoredListing(
        listing=listing,
        role_score=role_fit_score(listing, config.scoring.role_fit),
        visa_score=visa_eligibility_score(listing, config.scoring.visa),
        candidate_score=candidate_fit_score(listing, config.scoring.candidate),
    )


_SORT_KEYS = {
    "total":     lambda s: s.total,
    "role":      lambda s: s.role_score,
    "visa":      lambda s: s.visa_score,
    "candidate": lambda s: s.candidate_score,
}


def rank_listings(
    listings: list[RawListing],
    config: Config,
    sort_by: str = "total",
) -> list[ScoredListing]:
    """Score all listings and return them sorted by the chosen dimension."""
    if sort_by not in _SORT_KEYS:
        raise ValueError(f"sort_by must be one of: {list(_SORT_KEYS)}")
    scored = [score_listing(l, config) for l in listings]
    return sorted(scored, key=_SORT_KEYS[sort_by], reverse=True)
