import pytest
from store import init_db, upsert_listing, JobListing


def test_upsert_new_listing(tmp_db_path):
    init_db(tmp_db_path)

    data = {
        "source": "indeed",
        "external_id": "abc123",
        "title": "Software Engineer",
        "company": "Acme Corp",
        "location": "Vienna",
        "url": "https://indeed.com/viewjob?jk=abc123",
        "description": "",
        "salary": "",
        "posted_at": "",
    }

    listing, is_new = upsert_listing(data)
    assert is_new is True
    assert listing.title == "Software Engineer"
    assert JobListing.select().count() == 1


def test_upsert_existing_listing(tmp_db_path):
    init_db(tmp_db_path)

    data = {
        "source": "indeed",
        "external_id": "dup999",
        "title": "Backend Dev",
        "company": "Corp",
        "location": "",
        "url": "",
        "description": "",
        "salary": "",
        "posted_at": "",
    }

    _, first_new = upsert_listing(data)
    _, second_new = upsert_listing(data)

    assert first_new is True
    assert second_new is False
    assert JobListing.select().count() == 1


def test_different_sources_get_different_ids(tmp_db_path):
    init_db(tmp_db_path)

    base = {
        "external_id": "same123",
        "title": "Dev",
        "company": "X",
        "location": "",
        "url": "",
        "description": "",
        "salary": "",
        "posted_at": "",
    }

    _, n1 = upsert_listing({**base, "source": "indeed"})
    _, n2 = upsert_listing({**base, "source": "linkedin"})

    assert n1 is True
    assert n2 is True
    assert JobListing.select().count() == 2
