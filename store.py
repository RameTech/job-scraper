from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from peewee import (
    CharField,
    DateTimeField,
    Model,
    SqliteDatabase,
    TextField,
)

db = SqliteDatabase(None)


class JobListing(Model):
    id = CharField(primary_key=True)          # hash of source+external_id
    source = CharField()                       # "linkedin" | "indeed"
    external_id = CharField()
    title = CharField()
    company = CharField()
    location = CharField(default="")
    url = TextField()
    description = TextField(default="")
    salary = CharField(default="")
    posted_at = CharField(default="")         # raw string from site
    first_seen = DateTimeField(default=datetime.utcnow)
    last_seen = DateTimeField(default=datetime.utcnow)

    class Meta:
        database = db
        table_name = "job_listings"


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db.init(db_path, pragmas={"journal_mode": "wal", "foreign_keys": 1})
    db.connect(reuse_if_open=True)
    db.create_tables([JobListing], safe=True)


def _listing_id(source: str, external_id: str) -> str:
    return hashlib.sha1(f"{source}:{external_id}".encode()).hexdigest()[:16]


def upsert_listing(data: dict) -> tuple[JobListing, bool]:
    """Insert or update a listing. Returns (listing, is_new)."""
    lid = _listing_id(data["source"], data["external_id"])
    existing = JobListing.get_or_none(JobListing.id == lid)
    now = datetime.utcnow()

    if existing is None:
        listing = JobListing.create(id=lid, **data, first_seen=now, last_seen=now)
        return listing, True

    JobListing.update(last_seen=now).where(JobListing.id == lid).execute()
    return existing, False
