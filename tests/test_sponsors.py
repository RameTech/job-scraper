import pytest
from pathlib import Path
from sponsors import _normalize, is_sponsor, load_sponsor_set


def test_normalize_strips_legal_suffix():
    assert _normalize("Acme Ltd") == "acme"
    assert _normalize("Acme Limited") == "acme"
    assert _normalize("  Acme GROUP UK  ") == "acme"


def test_normalize_handles_unicode():
    # "Corp" and "Ltd" are stripped as legal suffixes, accent is ASCII-folded
    assert _normalize("Caf\u00e9 Corp Ltd") == "cafe"


def test_is_sponsor_with_real_csv():
    # Uses the actual data/sponsors.csv — must exist for this test to be meaningful
    csv_path = "data/sponsors.csv"
    if not Path(csv_path).exists():
        pytest.skip("sponsors.csv not present")

    # First company in the file (strip leading space from " A KARIM PHARMA LTD")
    assert is_sponsor("A KARIM PHARMA LTD", csv_path) is True


def test_is_sponsor_unknown_company():
    csv_path = "data/sponsors.csv"
    if not Path(csv_path).exists():
        pytest.skip("sponsors.csv not present")

    assert is_sponsor("Totally Fictional Company XYZ 99999", csv_path) is False


def test_is_sponsor_normalized_match():
    csv_path = "data/sponsors.csv"
    if not Path(csv_path).exists():
        pytest.skip("sponsors.csv not present")

    # Same company, different suffix casing — should still match
    assert is_sponsor("A Karim Pharma", csv_path) is True


def test_empty_csv(tmp_path):
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("Organisation Name,Town/City,County,Type & Rating,Route\n")
    assert is_sponsor("Any Company", str(csv_file)) is False
