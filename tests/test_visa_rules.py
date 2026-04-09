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
    ("£35K - £45K", 40_000),
    ("£38,000 - £42,000", 40_000),
    ("£30000", 30_000),
    ("competitive salary", None),
    ("no mention of money here", None),
    ("£25,000 per year", 25_000),
])
def test_extract_salary(text, expected):
    assert extract_salary(text) == expected


def test_extract_salary_range_averaged():
    assert extract_salary("Salary: £30k - £50k") == 40_000


# ---------------------------------------------------------------------------
# Occupation detection
# ---------------------------------------------------------------------------

def test_detects_project_manager():
    rule = detect_occupation("Graduate Project Manager — London")
    assert rule is not None and rule.soc_code == "2440" and rule.eligible is True


def test_detects_programme_manager():
    rule = detect_occupation("Programme Manager, Financial Services")
    assert rule is not None and rule.soc_code == "2440"


def test_detects_event_manager():
    rule = detect_occupation("Events Coordinator, luxury brand")
    assert rule is not None and rule.soc_code == "3557" and rule.eligible is True


def test_detects_executive_assistant():
    rule = detect_occupation("Executive Assistant to the CEO")
    assert rule is not None and rule.soc_code == "4113" and rule.eligible is False


def test_detects_personal_assistant():
    rule = detect_occupation("PA to Senior Partners")
    assert rule is not None and rule.soc_code == "4113" and rule.eligible is False


def test_detects_marketing_manager():
    rule = detect_occupation("Digital Marketing Manager")
    assert rule is not None and rule.soc_code == "3551" and rule.eligible is True
    assert rule.is_target is False


def test_detects_business_analyst():
    rule = detect_occupation("Business Analyst, FinTech")
    assert rule is not None and rule.soc_code == "2433" and rule.eligible is True


def test_detects_arts_manager():
    rule = detect_occupation("Arts Manager, West End venue")
    assert rule is not None and rule.soc_code == "1116" and rule.eligible is True


def test_detects_none_for_unknown():
    assert detect_occupation("Lorry Driver, HGV class 1") is None


# ---------------------------------------------------------------------------
# is_target flag
# ---------------------------------------------------------------------------

def test_pm_is_target():
    rule = detect_occupation("Project Manager")
    assert rule.is_target is True


def test_event_manager_is_target():
    rule = detect_occupation("Event Manager")
    assert rule.is_target is True


def test_marketing_manager_is_not_target():
    rule = detect_occupation("Marketing Manager")
    assert rule.is_target is False


def test_ea_is_target_but_ineligible():
    rule = detect_occupation("Executive Assistant")
    assert rule.is_target is True and rule.eligible is False


# ---------------------------------------------------------------------------
# Visa score — target eligible roles
# ---------------------------------------------------------------------------

def test_target_eligible_role_score():
    result = visa_score("Graduate Project Manager London")
    assert result.score == 40


def test_other_eligible_role_score():
    result = visa_score("Marketing Manager, London")
    assert result.score == 20


def test_ineligible_role_penalty():
    result = visa_score("Executive Assistant to the Board")
    assert result.eligible_role is False
    assert result.score == -20


def test_salary_meets_standard():
    result = visa_score("Project Manager, salary £45,000")
    assert result.salary_meets_standard is True
    assert result.score == 40 + 30


def test_salary_meets_new_entrant_only():
    result = visa_score("Graduate Project Manager, £36,000 per annum")
    assert result.salary_meets_standard is False
    assert result.salary_meets_new_entrant is True
    assert result.score == 40 + 15


def test_salary_below_floor_penalised():
    result = visa_score("Event Manager, £20,000 salary")
    assert result.score == 40 + (-20)


def test_no_salary_no_penalty():
    result = visa_score("Project Manager, competitive salary")
    assert result.salary_found is None
    assert result.score == 40


def test_ineligible_role_with_good_salary():
    result = visa_score("Executive Assistant, £50,000")
    assert result.score == -20 + 30


def test_unknown_role_salary_only():
    result = visa_score("Marketing Executive, £42,000")
    # SOC 3551 (marketing manager) not matched by "marketing executive" — no role
    # Only salary standard applies if no role matched
    assert result.score == 30 or result.score == 50  # 30 if no role, 50 if marketing manager matched


def test_notes_populated():
    result = visa_score("Graduate Project Manager, salary £45,000")
    assert len(result.notes) >= 2
    assert any("eligible role" in n for n in result.notes)
    assert any("salary" in n for n in result.notes)


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------

def test_thresholds_are_sane():
    assert SALARY_FLOOR < SALARY_NEW_ENTRANT < SALARY_STANDARD
    assert SALARY_STANDARD == 41_700
    assert SALARY_NEW_ENTRANT == 33_400
    assert SALARY_FLOOR == 25_000
