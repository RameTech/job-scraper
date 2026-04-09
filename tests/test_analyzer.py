import pytest
from scraper import RawListing
from analyzer import (
    passes_filters,
    filter_listings,
    role_fit_score,
    visa_eligibility_score,
    candidate_fit_score,
    score_listing,
    rank_listings,
    ScoredListing,
)
from config_schema import (
    Config,
    FiltersConfig,
    RoleFitConfig,
    VisaScoringConfig,
    CandidateFitConfig,
    ScoringConfig,
)


def make_listing(
    title: str = "Graduate Event Manager",
    company: str = "Corp",
    location: str = "London",
    description: str = "",
    source: str = "indeed",
) -> RawListing:
    return RawListing(
        source=source,
        external_id="x",
        title=title,
        company=company,
        location=location,
        description=description,
    )


# ---------------------------------------------------------------------------
# Hard filters
# ---------------------------------------------------------------------------

def test_passes_with_no_filters():
    assert passes_filters(make_listing(), Config()) is True


def test_excludes_title_keyword():
    cfg = Config(filters=FiltersConfig(exclude_keywords=["senior"]))
    assert passes_filters(make_listing(title="Senior Engineer"), cfg) is False
    assert passes_filters(make_listing(title="Junior Engineer"), cfg) is True


def test_location_filter_passes():
    cfg = Config(filters=FiltersConfig(require_location="London"))
    assert passes_filters(make_listing(location="London, UK"), cfg) is True
    assert passes_filters(make_listing(location="Greater London"), cfg) is True


def test_location_filter_drops_non_london():
    cfg = Config(filters=FiltersConfig(require_location="London"))
    assert passes_filters(make_listing(location="Manchester"), cfg) is False
    assert passes_filters(make_listing(location=""), cfg) is False


def test_no_visa_phrase_drops_listing():
    cfg = Config(filters=FiltersConfig(no_visa_phrases=["no visa sponsorship", "cannot sponsor"]))
    assert passes_filters(make_listing(description="We cannot sponsor."), cfg) is False
    assert passes_filters(make_listing(description="All welcome."), cfg) is True


def test_no_visa_phrase_case_insensitive():
    cfg = Config(filters=FiltersConfig(no_visa_phrases=["No Visa Sponsorship"]))
    assert passes_filters(make_listing(description="no visa sponsorship available"), cfg) is False


def test_no_visa_phrase_in_title():
    cfg = Config(filters=FiltersConfig(no_visa_phrases=["right to work"]))
    assert passes_filters(make_listing(title="Engineer — must have right to work in UK"), cfg) is False


# ---------------------------------------------------------------------------
# Score 1 — Role Fit
# ---------------------------------------------------------------------------

ROLE_CFG = RoleFitConfig(
    role_keywords=["project manager", "event manager", "executive assistant"],
    role_score=30,
    level_keywords=["graduate", "entry-level", "entry level"],
    level_score=20,
    language_keywords=["german", "german speaker"],
    language_score=50,
)


def test_role_score_zero_for_unrelated():
    assert role_fit_score(make_listing(title="Lorry Driver"), ROLE_CFG) == 0


def test_role_score_role_match():
    assert role_fit_score(make_listing(title="Project Manager"), ROLE_CFG) == 30


def test_role_score_level_match():
    assert role_fit_score(make_listing(title="Graduate Software Engineer"), ROLE_CFG) == 20


def test_role_score_language_bonus():
    assert role_fit_score(make_listing(title="Admin", description="German speaker preferred."), ROLE_CFG) == 50


def test_role_score_all_signals():
    # role(30) + level(20) + language(50) = 100
    listing = make_listing(title="Graduate Event Manager", description="German required.")
    assert role_fit_score(listing, ROLE_CFG) == 100


# ---------------------------------------------------------------------------
# Score 2 — Visa Eligibility (via analyzer wrapper)
# ---------------------------------------------------------------------------

VISA_CFG = VisaScoringConfig(
    eligible_role_score=40,
    other_eligible_score=20,
    salary_standard_score=30,
    salary_new_entrant_score=15,
    salary_below_floor_penalty=-20,
    ineligible_role_penalty=-20,
)


def test_visa_score_eligible_target_role():
    listing = make_listing(title="Project Manager")
    assert visa_eligibility_score(listing, VISA_CFG) == 40


def test_visa_score_other_eligible_role():
    listing = make_listing(title="Marketing Manager")
    assert visa_eligibility_score(listing, VISA_CFG) == 20


def test_visa_score_ineligible_role():
    listing = make_listing(title="Executive Assistant to the CEO")
    assert visa_eligibility_score(listing, VISA_CFG) == -20


def test_visa_score_salary_standard():
    listing = make_listing(title="Project Manager", description="Salary: £45,000")
    assert visa_eligibility_score(listing, VISA_CFG) == 40 + 30


def test_visa_score_no_role_detected():
    listing = make_listing(title="Office Assistant", description="No salary info.")
    assert visa_eligibility_score(listing, VISA_CFG) == 0


# ---------------------------------------------------------------------------
# Score 3 — Candidate Fit
# ---------------------------------------------------------------------------

CAND_CFG = CandidateFitConfig(
    crm_keywords=["crm", "salesforce"],
    crm_score=20,
    client_relations_keywords=["client relations", "account management"],
    client_relations_score=20,
    admin_coord_keywords=["administrative", "coordination"],
    admin_coord_score=15,
    sector_keywords=["events", "arts", "concert"],
    sector_score=20,
    data_reporting_keywords=["data analysis", "excel"],
    data_reporting_score=10,
    degree_relevance_keywords=["economics", "business"],
    degree_relevance_score=10,
    overqualified_keywords=["5+ years", "minimum 3 years"],
    overqualified_penalty=-20,
    team_management_keywords=["managing a team", "people management"],
    team_management_penalty=-15,
)


def test_candidate_score_zero_no_match():
    assert candidate_fit_score(make_listing(title="Lorry Driver"), CAND_CFG) == 0


def test_candidate_score_crm_match():
    assert candidate_fit_score(make_listing(description="Must know Salesforce CRM"), CAND_CFG) == 20


def test_candidate_score_sector_match():
    assert candidate_fit_score(make_listing(title="Events Coordinator"), CAND_CFG) == 20


def test_candidate_score_multiple_matches():
    # client relations(20) + sector(20) + crm(20) = 60
    listing = make_listing(
        title="Client Relations Executive — Events",
        description="Salesforce experience preferred.",
    )
    assert candidate_fit_score(listing, CAND_CFG) == 60


def test_candidate_score_overqualified_penalty():
    listing = make_listing(description="5+ years experience required.")
    assert candidate_fit_score(listing, CAND_CFG) == -20


def test_candidate_score_team_management_penalty():
    listing = make_listing(description="Role involves managing a team of 5.")
    assert candidate_fit_score(listing, CAND_CFG) == -15


def test_candidate_score_good_fit_with_penalty():
    # crm(20) + overqualified(-20) = 0
    listing = make_listing(description="CRM experience needed. 5+ years required.")
    assert candidate_fit_score(listing, CAND_CFG) == 0


def test_candidate_score_short_term_penalty():
    cfg = CandidateFitConfig(short_term_keywords=["internship", "12 month", "ftc", "fixed term"], short_term_penalty=-40)
    assert candidate_fit_score(make_listing(title="12 Month FTC Events Manager"), cfg) == -40
    assert candidate_fit_score(make_listing(title="Graduate Events Coordinator"), cfg) == 0


def test_candidate_score_short_term_variants():
    cfg = CandidateFitConfig(short_term_keywords=["internship", "12 month", "ftc", "fixed term", "maternity cover"], short_term_penalty=-40)
    assert candidate_fit_score(make_listing(title="Marketing Intern"), cfg) == 0  # "intern" not in list
    assert candidate_fit_score(make_listing(title="Marketing Internship"), cfg) == -40
    assert candidate_fit_score(make_listing(title="EA - Maternity Cover"), cfg) == -40
    assert candidate_fit_score(make_listing(description="This is a fixed term contract."), cfg) == -40


# ---------------------------------------------------------------------------
# ScoredListing total property
# ---------------------------------------------------------------------------

def test_scored_listing_total():
    sl = ScoredListing(listing=make_listing(), role_score=30, visa_score=40, candidate_score=20)
    assert sl.total == 90


# ---------------------------------------------------------------------------
# rank_listings — sort_by options
# ---------------------------------------------------------------------------

def _make_scored(role, visa, candidate) -> ScoredListing:
    return ScoredListing(
        listing=make_listing(),
        role_score=role,
        visa_score=visa,
        candidate_score=candidate,
    )


def test_rank_by_total():
    config = Config(scoring=ScoringConfig(role_fit=ROLE_CFG, visa=VISA_CFG, candidate=CAND_CFG))
    listings = [
        make_listing(title="Lorry Driver"),
        make_listing(title="Project Manager"),
        make_listing(title="Graduate Event Manager", description="German required."),
    ]
    ranked = rank_listings(listings, config, sort_by="total")
    totals = [s.total for s in ranked]
    assert totals == sorted(totals, reverse=True)


def test_rank_by_visa_only():
    config = Config(scoring=ScoringConfig(role_fit=ROLE_CFG, visa=VISA_CFG, candidate=CAND_CFG))
    listings = [
        make_listing(title="Marketing Manager", description="Salary £45,000"),  # visa: 20+30=50
        make_listing(title="Project Manager", description="Salary £45,000"),    # visa: 40+30=70
        make_listing(title="Lorry Driver"),                                       # visa: 0
    ]
    ranked = rank_listings(listings, config, sort_by="visa")
    visa_scores = [s.visa_score for s in ranked]
    assert visa_scores == sorted(visa_scores, reverse=True)


def test_rank_invalid_sort_raises():
    with pytest.raises(ValueError):
        rank_listings([], Config(), sort_by="invalid")
