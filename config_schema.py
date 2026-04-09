import os
import tomllib
from pathlib import Path
from pydantic import BaseModel, Field


class ScraperConfig(BaseModel):
    headless: bool = True
    timeout_ms: int = 30000
    max_listings_per_run: int = 100


class SearchConfig(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class FiltersConfig(BaseModel):
    min_salary: int = 0
    exclude_keywords: list[str] = Field(default_factory=list)
    sponsors_only: bool = False
    sponsors_csv: str = "data/sponsors.csv"
    require_location: str = ""                # e.g. "London" — drops listings without this in location
    no_visa_phrases: list[str] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    role_keywords: list[str] = Field(default_factory=list)
    role_score: int = 30
    level_keywords: list[str] = Field(default_factory=list)
    level_score: int = 20
    language_keywords: list[str] = Field(default_factory=list)
    language_score: int = 50


class StorageConfig(BaseModel):
    db_path: str = "data/jobs.db"


class Config(BaseModel):
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    # From .env
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
