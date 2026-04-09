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
# Eligible occupation codes (SOC 2020)
#
# is_target=True  → primary target roles (PM, Events) — score: eligible_role_score
# is_target=False → other eligible roles              — score: other_eligible_score
# eligible=False  → not sponsorable at all            — score: ineligible_role_penalty
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OccupationRule:
    key: str
    soc_code: str
    going_rate: int | None    # annual going rate in GBP; None = ineligible
    eligible: bool
    is_target: bool           # True = primary target role, False = other eligible
    label: str
    patterns: tuple[str, ...]


OCCUPATION_RULES: list[OccupationRule] = [
    # ------------------------------------------------------------------
    # Primary target roles (is_target=True)
    # ------------------------------------------------------------------
    OccupationRule(
        key="project_manager",
        soc_code="2440",
        going_rate=56_500,
        eligible=True,
        is_target=True,
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
        is_target=True,
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

    # ------------------------------------------------------------------
    # Other eligible roles (is_target=False) — +20 visa bonus
    # ------------------------------------------------------------------
    OccupationRule(
        key="marketing_manager",
        soc_code="3551",
        going_rate=38_700,
        eligible=True,
        is_target=False,
        label="Marketing Manager (SOC 3551)",
        patterns=(
            "marketing manager",
            "digital marketing manager",
            "marketing executive",
            "brand manager",
            "marketing director",
            "communications manager",
        ),
    ),
    OccupationRule(
        key="pr_communications",
        soc_code="3561",
        going_rate=36_000,
        eligible=True,
        is_target=False,
        label="PR & Communications Officer (SOC 3561)",
        patterns=(
            "pr manager",
            "public relations manager",
            "communications officer",
            "communications executive",
            "press officer",
            "media relations",
        ),
    ),
    OccupationRule(
        key="business_analyst",
        soc_code="2433",
        going_rate=47_000,
        eligible=True,
        is_target=False,
        label="Business / Data Analyst (SOC 2433)",
        patterns=(
            "business analyst",
            "business analysis",
            "data analyst",
            "operations analyst",
            "management consultant",
        ),
    ),
    OccupationRule(
        key="hr_manager",
        soc_code="1136",
        going_rate=44_000,
        eligible=True,
        is_target=False,
        label="HR Manager (SOC 1136)",
        patterns=(
            "hr manager",
            "human resources manager",
            "people manager",
            "hr business partner",
            "talent acquisition",
            "recruitment manager",
        ),
    ),
    OccupationRule(
        key="arts_culture_manager",
        soc_code="1116",
        going_rate=38_000,
        eligible=True,
        is_target=False,
        label="Arts & Culture Manager (SOC 1116)",
        patterns=(
            "arts manager",
            "culture manager",
            "gallery manager",
            "museum manager",
            "theatre manager",
            "venue manager",
            "cultural programme",
        ),
    ),
    OccupationRule(
        key="operations_manager",
        soc_code="1131",
        going_rate=48_000,
        eligible=True,
        is_target=False,
        label="Operations Manager (SOC 1131)",
        patterns=(
            "operations manager",
            "operations director",
            "head of operations",
            "chief of staff",
        ),
    ),
    OccupationRule(
        key="finance_analyst",
        soc_code="3534",
        going_rate=45_000,
        eligible=True,
        is_target=False,
        label="Finance & Investment Analyst (SOC 3534)",
        patterns=(
            "finance analyst",
            "financial analyst",
            "investment analyst",
            "financial controller",
            "fp&a",
        ),
    ),
    OccupationRule(
        key="it_manager",
        soc_code="2135",
        going_rate=56_000,
        eligible=True,
        is_target=False,
        label="IT Project / Programme Manager (SOC 2135)",
        patterns=(
            "it project manager",
            "it programme manager",
            "technology project manager",
            "scrum master",
            "agile coach",
            "product manager",
            "product owner",
        ),
    ),

    # ------------------------------------------------------------------
    # Ineligible roles (eligible=False)
    # ------------------------------------------------------------------
    OccupationRule(
        key="executive_assistant",
        soc_code="4113",
        going_rate=None,
        eligible=False,
        is_target=True,   # still a target role for search, just ineligible for visa
        label="Executive Assistant / PA (SOC 4113 — ineligible for Skilled Worker visa)",
        patterns=(
            "executive assistant",
            "ea to ",
            "ea to the",
            "personal assistant",
            "pa to ",
            "pa to the",
        ),
    ),
]


# ---------------------------------------------------------------------------
# Salary extraction
# ---------------------------------------------------------------------------

_SALARY_RE = re.compile(r"£\s*(\d[\d,]*)\s*[kK]?\b", re.IGNORECASE)


def _parse_value(raw: str) -> float:
    return float(raw.replace(",", "").strip())


def extract_salary(text: str) -> int | None:
    """
    Return the best-guess *annual* salary (GBP) from free text, or None.
    Handles ranges (averages them), k-suffix, and bare numbers.
    """
    matches = _SALARY_RE.findall(text)
    if not matches:
        return None

    values: list[float] = []
    for m in matches[:2]:
        v = _parse_value(m)
        idx = text.find(f"£{m}")
        has_k = False
        if idx != -1:
            after = text[idx + len(m) + 1 : idx + len(m) + 3].strip().lower()
            has_k = after.startswith("k")
        if has_k or v < 1_000:
            v *= 1_000
        values.append(v)

    return int(sum(values) / len(values)) if values else None


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
    eligible_role: bool | None      # None = no role detected
    is_target_role: bool | None
    salary_found: int | None
    salary_meets_standard: bool | None
    salary_meets_new_entrant: bool | None
    occupation: OccupationRule | None
    notes: list[str]


def visa_score(
    text: str,
    eligible_role_score: int = 40,       # target eligible role (PM, Events)
    other_eligible_score: int = 20,      # any other eligible SOC code
    salary_standard_score: int = 30,     # salary >= £41,700
    salary_new_entrant_score: int = 15,  # salary >= £33,400 (graduate rate)
    salary_below_floor_penalty: int = -20,
    ineligible_role_penalty: int = -20,  # role SOC is not sponsorable
) -> VisaScoreBreakdown:
    """
    Score a job listing's visa sponsorship likelihood.

    Points:
        +eligible_role_score     primary target role (PM / Events) with eligible SOC
        +other_eligible_score    other role with eligible SOC code
        ineligible_role_penalty  role SOC is not sponsorable (e.g. EA/PA)
        +salary_standard_score   salary >= £41,700
        +salary_new_entrant_score salary >= £33,400 (graduate/under-26 only)
        salary_below_floor_penalty salary explicitly < £25,000
    """
    score = 0
    notes: list[str] = []

    occupation = detect_occupation(text)
    salary = extract_salary(text)

    # Role eligibility
    if occupation is not None:
        if occupation.eligible:
            if occupation.is_target:
                score += eligible_role_score
                notes.append(f"+{eligible_role_score} target eligible role: {occupation.label}")
            else:
                score += other_eligible_score
                notes.append(f"+{other_eligible_score} eligible role: {occupation.label}")
        else:
            score += ineligible_role_penalty
            notes.append(f"{ineligible_role_penalty} ineligible role: {occupation.label}")

    # Salary vs thresholds
    salary_meets_standard = None
    salary_meets_new_entrant = None
    if salary is not None:
        salary_meets_standard = salary >= SALARY_STANDARD
        salary_meets_new_entrant = salary >= SALARY_NEW_ENTRANT

        if salary_meets_standard:
            score += salary_standard_score
            notes.append(
                f"+{salary_standard_score} salary £{salary:,} >= standard £{SALARY_STANDARD:,}"
            )
        elif salary_meets_new_entrant:
            score += salary_new_entrant_score
            notes.append(
                f"+{salary_new_entrant_score} salary £{salary:,} meets graduate rate £{SALARY_NEW_ENTRANT:,}"
            )
        elif salary < SALARY_FLOOR:
            score += salary_below_floor_penalty
            notes.append(
                f"{salary_below_floor_penalty} salary £{salary:,} below floor £{SALARY_FLOOR:,}"
            )
        else:
            notes.append(f"salary £{salary:,} between floor and graduate threshold — marginal")

    return VisaScoreBreakdown(
        score=score,
        eligible_role=occupation.eligible if occupation else None,
        is_target_role=occupation.is_target if occupation else None,
        salary_found=salary,
        salary_meets_standard=salary_meets_standard,
        salary_meets_new_entrant=salary_meets_new_entrant,
        occupation=occupation,
        notes=notes,
    )
