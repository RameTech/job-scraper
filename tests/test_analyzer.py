import pytest
from scraper import RawListing
from analyzer import passes_filters, filter_listings, score_listing, rank_listings
from config_schema import Config, FiltersConfig, ScoringConfig


def make_listing(
    title: str = "Graduate Project Manager",
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
# Filter tests
# ---------------------------------------------------------------------------

def test_passes_with_no_filters():
    config = Config()
    assert passes_filters(make_listing(), config) is True


def test_excludes_title_keyword():
    config = Config(filters=FiltersConfig(exclude_keywords=["senior"]))
    assert passes_filters(make_listing(title="Senior Engineer"), config) is False
    assert passes_filters(make_listing(title="Junior Engineer"), config) is True


def test_location_filter_passes():
    config = Config(filters=FiltersConfig(require_location="London"))
    assert passes_filters(make_listing(location="London, UK"), config) is True
    assert passes_filters(make_listing(location="Greater London"), config) is True


def test_location_filter_drops_non_london():
    config = Config(filters=FiltersConfig(require_location="London"))
    assert passes_filters(make_listing(location="Manchester"), config) is False
    assert passes_filters(make_listing(location=""), config) is False


def test_no_visa_phrase_drops_listing():
    phrases = ["no visa sponsorship", "cannot sponsor"]
    config = Config(filters=FiltersConfig(no_visa_phrases=phrases))

    dropped = make_listing(description="We cannot sponsor visa applications.")
    kept = make_listing(description="We welcome all candidates.")

    assert passes_filters(dropped, config) is False
    assert passes_filters(kept, config) is True


def test_no_visa_phrase_case_insensitive():
    config = Config(filters=FiltersConfig(no_visa_phrases=["No Visa Sponsorship"]))
    listing = make_listing(description="Please note: no visa sponsorship available.")
    assert passes_filters(listing, config) is False


def test_no_visa_phrase_in_title():
    config = Config(filters=FiltersConfig(no_visa_phrases=["right to work"]))
    listing = make_listing(title="Engineer - must have right to work in UK")
    assert passes_filters(listing, config) is False


# ---------------------------------------------------------------------------
# Scoring tests
# ---------------------------------------------------------------------------

SCORING = ScoringConfig(
    role_keywords=["project manager", "event manager", "executive assistant"],
    role_score=30,
    level_keywords=["graduate", "entry-level", "entry level"],
    level_score=20,
    language_keywords=["german", "german speaker"],
    language_score=50,
)


def test_score_zero_for_unrelated():
    # Lorry Driver: no role/level/language match, no visa SOC match → 0
    listing = make_listing(title="Lorry Driver", description="CDL required.")
    assert score_listing(listing, SCORING) == 0


def test_score_role_match():
    # role_score(30) + visa eligible role(40) = 70
    listing = make_listing(title="Project Manager")
    assert score_listing(listing, SCORING) == 70


def test_score_level_match():
    # level_score(20) only — "Graduate Software Engineer" has no visa SOC match
    listing = make_listing(title="Graduate Software Engineer")
    assert score_listing(listing, SCORING) == 20


def test_score_language_bonus():
    # language_score(50) only — "Office Administrator" has no visa SOC match
    listing = make_listing(title="Office Administrator", description="German speaker preferred.")
    assert score_listing(listing, SCORING) == 50


def test_score_combines_signals():
    # role(30) + level(20) + language(50) + visa eligible role(40) = 140
    listing = make_listing(
        title="Graduate Event Manager",
        description="German speaker required.",
    )
    assert score_listing(listing, SCORING) == 140


def test_rank_listings_sorted_best_first():
    config = Config(scoring=SCORING)
    listings = [
        make_listing(title="Lorry Driver"),                                    # score 0
        make_listing(title="Project Manager"),                                 # score 70
        make_listing(title="Graduate Event Manager",
                     description="German required."),                          # score 140
    ]
    ranked = rank_listings(listings, config)
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 140
