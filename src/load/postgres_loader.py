import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, execute_values

from src.config import PROJECT_ROOT


POSTING_COLUMNS = [
    "source", "job_id", "job_title", "company_name", "location", "country",
    "description", "salary_min", "salary_max", "currency", "contract_type",
    "category", "redirect_url", "created_at", "search_role", "search_country",
    "raw_json", "extract_date",
]

OBSERVATION_COLUMNS = ["source", "job_id", "search_role", "search_country", "extract_date"]


def get_connection():
    load_dotenv(PROJECT_ROOT / ".env")

    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        connect_timeout=10,
    )


def first_per_job(jobs: list[dict]) -> list[dict]:
    # An archive can repeat a job id across pages. Keep the first one,
    # which is what the earlier row-by-row load kept.
    first_jobs = {}
    for job in jobs:
        first_jobs.setdefault((job["source"], job["job_id"]), job)
    return list(first_jobs.values())


def insert_job_postings(cursor, jobs: list[dict]) -> int:
    if not jobs:
        return 0

    rows = [
        tuple(Json(job[column]) if column == "raw_json" else job[column] for column in POSTING_COLUMNS)
        for job in jobs
    ]
    # The catalogue keeps the first version of each posting; later versions
    # are only recorded as observations (see README).
    inserted = execute_values(
        cursor,
        f"""
        INSERT INTO raw.job_postings ({", ".join(POSTING_COLUMNS)})
        VALUES %s
        ON CONFLICT (source, job_id) DO NOTHING
        RETURNING job_id
        """,
        rows,
        page_size=1000,
        fetch=True,
    )
    return len(inserted)


def insert_job_posting_observations(cursor, jobs: list[dict]) -> int:
    if not jobs:
        return 0

    rows = [tuple(job[column] for column in OBSERVATION_COLUMNS) for job in jobs]
    inserted = execute_values(
        cursor,
        f"""
        INSERT INTO raw.job_posting_observations ({", ".join(OBSERVATION_COLUMNS)})
        VALUES %s
        ON CONFLICT (source, job_id, search_country, search_role, extract_date) DO NOTHING
        RETURNING job_id
        """,
        rows,
        page_size=1000,
        fetch=True,
    )
    return len(inserted)


def load_segment(connection, jobs: list[dict]) -> tuple[int, int]:
    """Insert one segment's postings and observations in a single transaction."""
    unique_jobs = first_per_job(jobs)

    # In psycopg2, "with connection" commits on success and rolls back on error.
    # It does not close the connection; the caller does that.
    with connection:
        with connection.cursor() as cursor:
            posting_count = insert_job_postings(cursor, unique_jobs)
            observation_count = insert_job_posting_observations(cursor, unique_jobs)

    return posting_count, observation_count
