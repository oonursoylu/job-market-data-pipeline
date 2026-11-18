"""Shared settings for the extraction and load steps.

Countries and search roles live in the dbt seeds, so Python and dbt read the
same list. To add a country or role, add one row to the matching seed file.
"""
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / "adzuna"
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_job_market"
SEEDS_DIR = DBT_PROJECT_DIR / "seeds"
LOG_DIR = PROJECT_ROOT / "logs"

# Collection defaults: up to 3 pages of 50 results per country and role.
MAX_PAGES = 3
RESULTS_PER_PAGE = 50
REQUEST_PAUSE_SECONDS = 1.5

# A segment left "in_progress" for longer than this cannot still be running: the scheduled
# task is stopped after one hour and never runs twice at once (register_scheduled_task.ps1).
# Such a segment is retried like a failed one.
STALE_IN_PROGRESS_AFTER = timedelta(hours=1)

# Each pipeline run also loads archived days from this many days back that are not fully
# in PostgreSQL, for example after the database was down during both runs of a day.
CATCH_UP_DAYS = 14

# Adzuna's Search API returns a description snippet, not full advert text.
DESCRIPTION_CONTRACT = "snippet"
DESCRIPTION_TRUNCATION_BOUNDARY = 500


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    start_date: date


@dataclass(frozen=True)
class Role:
    code: str
    search_term: str
    name: str
    start_date: date


def _read_seed(file_name: str) -> list[dict]:
    with (SEEDS_DIR / file_name).open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def load_countries() -> list[Country]:
    rows = sorted(_read_seed("search_countries.csv"), key=lambda row: int(row["country_sort_order"]))
    return [
        Country(row["search_country"], row["country_name"], date.fromisoformat(row["collection_start_date"]))
        for row in rows
    ]


def load_roles() -> list[Role]:
    rows = sorted(_read_seed("search_roles.csv"), key=lambda row: int(row["role_sort_order"]))
    return [
        Role(row["search_role"], row["search_term"], row["role_name"], date.fromisoformat(row["collection_start_date"]))
        for row in rows
    ]


COUNTRIES = load_countries()
ROLES = load_roles()
COUNTRY_CODES = [country.code for country in COUNTRIES]
ROLE_CODES = [role.code for role in ROLES]
SEARCH_TERMS = {role.code: role.search_term for role in ROLES}


def expected_segments(extract_date: date, countries=None, roles=None) -> list[tuple[str, str]]:
    """Country and role pairs that were collected on a date, in run order.

    A segment is expected from the later of its country and role start dates.
    """
    countries = countries or COUNTRY_CODES
    roles = roles or ROLE_CODES
    country_starts = {country.code: country.start_date for country in COUNTRIES}
    role_starts = {role.code: role.start_date for role in ROLES}
    return [
        (country, role)
        for country in countries
        for role in roles
        if extract_date >= max(country_starts[country], role_starts[role])
    ]


def archive_dir(country: str, role: str, extract_date: date) -> Path:
    return RAW_DATA_DIR / f"country={country}" / f"search_role={role}" / f"date={extract_date.isoformat()}"


def archive_path(country: str, role: str, extract_date: date) -> Path:
    return archive_dir(country, role, extract_date) / "jobs.jsonl"


def status_path(country: str, role: str, extract_date: date) -> Path:
    return archive_dir(country, role, extract_date) / "extraction_status.json"
