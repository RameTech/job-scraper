import os
import tomllib
from pathlib import Path
from pydantic import BaseModel, Field


class ScraperConfig(BaseModel):
    headless: bool = True
    timeout_ms: int = 30000
    max_listings_per_run: int = 100
    description_concurrency: int = 4   # parallel description page fetches


class SearchConfig(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class FiltersConfig(BaseModel):
    min_salary: int = 0
    exclude_keywords: list[str] = Field(default_factory=list)
    sponsors_only: bool = False
    sponsors_csv: str = "data/sponsors.csv"
    require_location: str = ""
    no_visa_phrases: list[str] = Field(default_factory=list)


class VisaScoringConfig(BaseModel):
    eligible_role_score: int = 40        # target eligible role (PM, Events)
    other_eligible_score: int = 20       # any other eligible SOC code
    salary_standard_score: int = 30      # salary >= £41,700
    salary_new_entrant_score: int = 15   # salary >= £33,400
    salary_below_floor_penalty: int = -20
    ineligible_role_penalty: int = -20


class RoleFitConfig(BaseModel):
    """Does this job posting match the roles we are targeting?"""
    role_keywords: list[str] = Field(default_factory=list)
    role_score: int = 30
    level_keywords: list[str] = Field(default_factory=list)
    level_score: int = 20
    language_keywords: list[str] = Field(default_factory=list)
    language_score: int = 50


class CandidateFitConfig(BaseModel):
    """How well does the candidate's profile match this specific job?"""
    # Keyword groups mapped to score deltas (positive = good fit, negative = mismatch)
    crm_keywords: list[str] = Field(default_factory=list)
    crm_score: int = 20

    client_relations_keywords: list[str] = Field(default_factory=list)
    client_relations_score: int = 20

    admin_coord_keywords: list[str] = Field(default_factory=list)
    admin_coord_score: int = 15

    sector_keywords: list[str] = Field(default_factory=list)
    sector_score: int = 20

    data_reporting_keywords: list[str] = Field(default_factory=list)
    data_reporting_score: int = 10

    degree_relevance_keywords: list[str] = Field(default_factory=list)
    degree_relevance_score: int = 10

    # Penalty signals — job requires experience/seniority Martha doesn't have
    overqualified_keywords: list[str] = Field(default_factory=list)
    overqualified_penalty: int = -20

    team_management_keywords: list[str] = Field(default_factory=list)
    team_management_penalty: int = -15

    # Penalty signals — short-term / temporary roles (incompatible with relocation)
    short_term_keywords: list[str] = Field(default_factory=list)
    short_term_penalty: int = -40


class ScoringConfig(BaseModel):
    role_fit: RoleFitConfig = Field(default_factory=RoleFitConfig)
    visa: VisaScoringConfig = Field(default_factory=VisaScoringConfig)
    candidate: CandidateFitConfig = Field(default_factory=CandidateFitConfig)


class StorageConfig(BaseModel):
    db_path: str = "data/jobs.db"


class Config(BaseModel):
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    linkedin_email: str = ""
    linkedin_password: str = ""


def load_config(config_path: str = "config.toml") -> Config:
    path = Path(config_path)
    raw: dict = {}
    if path.exists():
        with open(path, "rb") as f:
            raw = tomllib.load(f)

    cfg = Config(**raw)
    cfg.linkedin_email = os.getenv("LINKEDIN_EMAIL", "")
    cfg.linkedin_password = os.getenv("LINKEDIN_PASSWORD", "")
    return cfg
