import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json


def get_connection():
    load_dotenv()

    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def insert_job_postings(jobs: list[dict]) -> int:
    insert_sql = """
        INSERT INTO raw.job_postings (
            source,
            job_id,
            job_title,
            company_name,
            location,
            country,
            description,
            salary_min,
            salary_max,
            currency,
            contract_type,
            category,
            redirect_url,
            created_at,
            search_role,
            search_country,
            raw_json,
            extract_date
        )
        VALUES (
            %(source)s,
            %(job_id)s,
            %(job_title)s,
            %(company_name)s,
            %(location)s,
            %(country)s,
            %(description)s,
            %(salary_min)s,
            %(salary_max)s,
            %(currency)s,
            %(contract_type)s,
            %(category)s,
            %(redirect_url)s,
            %(created_at)s,
            %(search_role)s,
            %(search_country)s,
            %(raw_json)s,
            %(extract_date)s
        )
        ON CONFLICT (source, job_id) DO NOTHING;
    """

    inserted_count = 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            for job in jobs:
                job_to_insert = job.copy()
                job_to_insert["raw_json"] = Json(job_to_insert["raw_json"])

                cursor.execute(insert_sql, job_to_insert)
                inserted_count += cursor.rowcount

    return inserted_count


def insert_job_posting_observations(jobs: list[dict]) -> int:
    insert_sql = """
        INSERT INTO raw.job_posting_observations (
            source,
            job_id,
            search_role,
            search_country,
            extract_date
        )
        VALUES (
            %(source)s,
            %(job_id)s,
            %(search_role)s,
            %(search_country)s,
            %(extract_date)s
        )
        ON CONFLICT (
            source,
            job_id,
            search_country,
            search_role,
            extract_date
        ) DO NOTHING;
    """

    inserted_count = 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            for job in jobs:
                cursor.execute(insert_sql, job)
                inserted_count += cursor.rowcount

    return inserted_count
