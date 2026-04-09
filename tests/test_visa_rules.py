import pytest
from visa_rules import (
    extract_salary,
    detect_occupation,
    visa_score,
    SALARY_STANDARD,
    SALARY_NEW_ENTRANT,
    SALARY_FLOOR,
)


# ---------------------------------------------------------------------------
# Salary extraction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Salary: £45,000 per annum", 45_000),
    ("Up to £50k", 50_000),
    ("£35K - £45K", 40_000),          # average of range
    ("£38,000 - £42,000", 40_000),    # average of range
    ("£30000", 30_000),
    ("competitive salary", None),
    ("no mention of money here", None),
    ("£25,000 per year", 25_000),
])
def test_extract_salary(text, expected):
    result = extract_salary(text)
    assert result == expected


def test_extract_salary_range_averaged():
    # £30k - £50k → average 40,000
    result = extract_salary("Salary: £30k - £50k")
    assert result == 40_000


# ---------------------------------------------------------------------------
# Occupation detection
# ---------------------------------------------------------------------------

def test_detects_project_manager():
    rule = detect_occupation("Graduate Project Manager — London")
    assert rule is not None
    assert rule.soc_code == "2440"
    assert rule.eligible is True


def test_detects_programme_manager():
    rule = detect_occupation("Programme Manager, Financial Services")
    assert rule is not None
    assert rule.soc_code == "2440"


def test_detects_event_manager():
    rule = detect_occupation("Events Coordinator, luxury brand")
    assert rule is not None
    assert rule.soc_code == "3557"
    assert rule.eligible is True


def test_detects_executive_assistant():
    rule = detect_occupation("Executive Assistant to the CEO")
    assert rule is not None
    assert rule.soc_code == "4113"
    assert rule.eligible is False


def test_detects_personal_assistant():
    rule = detect_occupation("PA to Senior Partners — City law firm")
    assert rule is not None
    assert rule.soc_code == "4113"
    assert rule.eligible is False


def test_detects_none_for_unknown():
    rule = detect_occupation("Lorry Driver, HGV class 1")
    assert rule is None


# ---------------------------------------------------------------------------
# Visa score — eligible roles
# ---------------------------------------------------------------------------

def test_eligible_role_adds_score():
    result = visa_score("Graduate Project Manager London")
    assert result.eligible_role is True
    assert result.score >= 40


def test_ineligible_role_subtracts_score():
    result = visa_score("Executive Assistant to the Board")
    assert result.eligible_role is False
    assert result.score <= -20


def test_salary_meets_standard():
    result = visa_score("Project Manager, salary £45,000")
    assert result.salary_meets_standard is True
    assert result.score >= 40 + 30   # eligible role + standard salary


def test_salary_meets_new_entrant_only():
    result = visa_score("Graduate Project Manager, £36,000 per annum")
    assert result.salary_meets_standard is False
    assert result.salary_meets_new_entrant is True
    assert result.score >= 40 + 15   # eligible role + new-entrant bonus


def test_salary_below_floor_penalised():
    result = visa_score("Event Manager, £20,000 salary")
    assert result.salary_found == 20_000
    assert result.salary_meets_new_entrant is False
    # Should have eligible-role bonus but floor penalty
    assert result.score == 40 + (-20)


def test_no_salary_no_penalty():
    # Eligible role, no salary mentioned — no salary deduction
    result = visa_score("Project Manager, competitive salary")
    assert result.salary_found is None
    assert result.score == 40   # just the role bonus


def test_ineligible_role_with_good_salary():
    # EA with £50k — still ineligible role, salary bonus irrelevant (but still scored)
    result = visa_score("Executive Assistant, £50,000")
    assert result.eligible_role is False
    # ineligible penalty + standard salary bonus
    assert result.score == -20 + 30


def test_unknown_role_no_role_points():
    result = visa_score("Marketing Executive, £42,000")
    assert result.eligible_role is None
    assert result.score == 30   # only salary standard bonus, no role signal


def test_notes_are_populated():
    result = visa_score("Graduate Project Manager, salary £45,000")
    assert len(result.notes) >= 2
    assert any("eligible role" in n for n in result.notes)
    assert any("salary" in n for n in result.notes)


# ---------------------------------------------------------------------------
# Threshold constants sanity check
# ---------------------------------------------------------------------------

def test_thresholds_are_sane():
    assert SALARY_FLOOR < SALARY_NEW_ENTRANT < SALARY_STANDARD
    assert SALARY_STANDARD == 41_700
    assert SALARY_NEW_ENTRANT == 33_400
    assert SALARY_FLOOR == 25_000
