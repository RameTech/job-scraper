import pytest
from scraper import RawListing
from analyzer import passes_filters, filter_listings
from config_schema import Config, FiltersConfig


def make_listing(title: str, source: str = "indeed") -> RawListing:
    return RawListing(
        source=source,
        external_id="x",
        title=title,
        company="Corp",
    )


def test_passes_no_filters():
    config = Config()
    listing = make_listing("Software Engineer")
    assert passes_filters(listing, config) is True


def test_excludes_keyword():
    config = Config(filters=FiltersConfig(exclude_keywords=["senior"]))
    assert passes_filters(make_listing("Senior Engineer"), config) is False
    assert passes_filters(make_listing("Junior Engineer"), config) is True


def test_filter_listings_removes_excluded():
    config = Config(filters=FiltersConfig(exclude_keywords=["lead"]))
    listings = [
        make_listing("Tech Lead"),
        make_listing("Backend Developer"),
        make_listing("Lead Architect"),
    ]
    result = filter_listings(listings, config)
    assert len(result) == 1
    assert result[0].title == "Backend Developer"
