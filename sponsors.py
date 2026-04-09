"""Load and query the UK visa sponsor register."""
from __future__ import annotations

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation/noise for fuzzy matching."""
    name = name.strip().lower()
    # Normalize unicode (e.g. smart quotes, accented chars)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    # Remove legal suffixes that differ between job boards and the register
    name = re.sub(
        r"\b(ltd|limited|llp|llc|plc|inc|corp|group|uk|t/a.*|trading as.*)\b",
        "",
        name,
    )
    # Strip non-alphanumeric
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


@lru_cache(maxsize=1)
def load_sponsor_set(csv_path: str = "data/sponsors.csv") -> frozenset[str]:
    """Return a frozenset of normalized sponsor names. Cached after first load."""
    path = Path(csv_path)
    if not path.exists():
        return frozenset()

    names: set[str] = set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("Organisation Name", "")
            norm = _normalize(raw)
            if norm:
                names.add(norm)
    return frozenset(names)


def is_sponsor(company_name: str, csv_path: str = "data/sponsors.csv") -> bool:
    """Return True if company_name matches a visa sponsor (normalized match)."""
    sponsors = load_sponsor_set(csv_path)
    return _normalize(company_name) in sponsors
