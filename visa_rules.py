"""
UK Skilled Worker visa eligibility rules (current as of July 2025).

Sources:
  https://www.gov.uk/skilled-worker-visa/your-job
  https://www.gov.uk/skilled-worker-visa/when-you-can-be-paid-less
  https://www.gov.uk/government/publications/skilled-worker-visa-eligible-occupations
  https://www.gov.uk/government/publications/skilled-worker-visa-going-rates-for-eligible-occupations
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Salary thresholds (April / July 2025 rules)
# ---------------------------------------------------------------------------

SALARY_STANDARD = 41_700     # General Skilled Worker minimum
SALARY_NEW_ENTRANT = 33_400  # Under-26 / recent graduate / career switcher
SALARY_FLOOR = 25_000        # Absolute floor (raised 9 April 2025)


# ---------------------------------------------------------------------------
# Eligible occupation codes (SOC 2020) — subset relevant to this scraper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OccupationRule:
    key: str
    soc_code: str
    going_rate: int | None   # annual going rate in GBP; None = ineligible
    eligible: bool
    label: str
    patterns: tuple[str, ...]


OCCUPATION_RULES: list[OccupationRule] = [
    OccupationRule(
        key="project_manager",
        soc_code="2440",
        going_rate=56_500,
        eligible=True,
        label="Project Manager (SOC 2440)",
        patterns=(
            "project manager",
            "project management",
            "programme manager",
            "program manager",
            "project director",
            "delivery manager",
        ),
    ),
    OccupationRule(
        key="event_manager",
        soc_code="3557",
        going_rate=33_400,
        eligible=True,
        label="Event Manager (SOC 3557)",
        patterns=(
            "event manager",
            "events manager",
            "event management",
            "events coordinator",
            "events director",
            "conference manager",
            "conference coordinator",
        ),
    ),
    OccupationRule(
        key="executive_assistant",
        soc_code="4113",
        going_rate=None,
        eligible=False,
        label="Executive Assistant / PA (SOC 4113 — ineligible for Skilled Worker visa)",
        patterns=(
            "executive assistant",
            "ea to ",
            "ea to the",
            "personal assistant",
            "pa to ",
            "pa to the",
            "office manager",
        ),
    ),
]


# ---------------------------------------------------------------------------
# Salary extraction
# ---------------------------------------------------------------------------

# Matches: £35,000 / £35k / £35K / £35,000 - £45,000 / up to £50k / £30000
_SALARY_RE = re.compile(
    r"£\s*(\d[\d,]*)\s*[kK]?\b",
    re.IGNORECASE,
)


def _parse_value(raw: str) -> float:
    """Convert a raw salary string to an annual float (handles k suffix)."""
    raw = raw.replace(",", "").strip()
    return float(raw)


def extract_salary(text: str) -> int | None:
    """
    Return the best-guess *annual* salary (GBP) from free text, or None.

    Strategy: find all £ values, treat values < 1000 as 'k' (thousands),
    return the average of up to two values (handles salary ranges).
    """
    matches = _SALARY_RE.findall(text)
    if not matches:
        return None

    values: list[float] = []
    for m in matches[:2]:  # take at most two (range)
        v = _parse_value(m)
        # Heuristic: if the original text had a 'k' suffix after this number
        idx = text.find(f"£{m}")
        has_k = False
        if idx != -1:
            after = text[idx + len(m) + 1 : idx + len(m) + 3].strip().lower()
            has_k = after.startswith("k")
        if has_k or v < 1_000:
            v *= 1_000
        values.append(v)

    if not values:
        return None
    return int(sum(values) / len(values))


# ---------------------------------------------------------------------------
# Role detection
# ---------------------------------------------------------------------------

def detect_occupation(text: str) -> OccupationRule | None:
    """Return the first matching OccupationRule found in text, or None."""
    lower = text.lower()
    for rule in OCCUPATION_RULES:
        if any(p in lower for p in rule.patterns):
            return rule
    return None


# ---------------------------------------------------------------------------
# Visa score
# ---------------------------------------------------------------------------

@dataclass
class VisaScoreBreakdown:
    score: int
    eligible_role: bool | None   # None = unknown (no role detected)
    salary_found: int | None
    salary_meets_standard: bool | None
    salary_meets_new_entrant: bool | None
    occupation: OccupationRule | None
    notes: list[str]


def visa_score(
    text: str,
    eligible_role_score: int = 40,
    salary_standard_score: int = 30,
    salary_new_entrant_score: int = 15,
    salary_below_floor_penalty: int = -20,
    ineligible_role_penalty: int = -20,
) -> VisaScoreBreakdown:
    """
    Score a job listing's visa sponsorship likelihood.

    Points:
        +eligible_role_score         role SOC code is sponsorable
        +salary_standard_score       salary >= £41,700 (standard threshold)
        +salary_new_entrant_score    salary >= £33,400 (new entrant / graduate rate)
        ineligible_role_penalty      role SOC is not sponsorable (e.g. EA/PA)
        salary_below_floor_penalty   salary explicitly below £25,000 floor

    Salary and role signals are independent — both fire if both are detected.
    If no salary is found, no salary points are added or deducted.
    """
    score = 0
    notes: list[str] = []

    occupation = detect_occupation(text)
    salary = extract_salary(text)

    # Role eligibility
    if occupation is not None:
        if occupation.eligible:
            score += eligible_role_score
            notes.append(f"+{eligible_role_score} eligible role: {occupation.label}")
        else:
            score += ineligible_role_penalty
            notes.append(
                f"{ineligible_role_penalty} ineligible role: {occupation.label}"
            )

    # Salary vs thresholds
    salary_meets_standard = None
    salary_meets_new_entrant = None
    if salary is not None:
        salary_meets_standard = salary >= SALARY_STANDARD
        salary_meets_new_entrant = salary >= SALARY_NEW_ENTRANT

        if salary_meets_standard:
            score += salary_standard_score
            notes.append(
                f"+{salary_standard_score} salary £{salary:,} >= standard threshold £{SALARY_STANDARD:,}"
            )
        elif salary_meets_new_entrant:
            score += salary_new_entrant_score
            notes.append(
                f"+{salary_new_entrant_score} salary £{salary:,} meets new-entrant rate £{SALARY_NEW_ENTRANT:,} "
                f"(graduates/under-26 only)"
            )
        elif salary < SALARY_FLOOR:
            score += salary_below_floor_penalty
            notes.append(
                f"{salary_below_floor_penalty} salary £{salary:,} below absolute floor £{SALARY_FLOOR:,}"
            )
        else:
            notes.append(
                f"salary £{salary:,} is between floor and new-entrant threshold — marginal"
            )

    return VisaScoreBreakdown(
        score=score,
        eligible_role=occupation.eligible if occupation else None,
        salary_found=salary,
        salary_meets_standard=salary_meets_standard,
        salary_meets_new_entrant=salary_meets_new_entrant,
        occupation=occupation,
        notes=notes,
    )
