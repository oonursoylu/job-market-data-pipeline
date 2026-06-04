from datetime import date
from pathlib import Path

from job_mapper import map_adzuna_job
from jsonl_reader import read_jsonl
from postgres_loader import insert_job_postings


def run_load(file_path: str | Path, search_role: str, search_country: str, extract_date: date) -> None:
    raw_jobs = read_jsonl(file_path)

    mapped_jobs = [
        map_adzuna_job(
            job=job,
            search_role=search_role,
            search_country=search_country,
            extract_date=extract_date,
        )
        for job in raw_jobs
    ]

    inserted_count = insert_job_postings(mapped_jobs)
    duplicate_count = len(mapped_jobs) - inserted_count

    print(f"Read records: {len(raw_jobs)}")
    print(f"Mapped records: {len(mapped_jobs)}")
    print(f"Inserted records: {inserted_count}")
    print(f"Skipped duplicates: {duplicate_count}")


if __name__ == "__main__":
    search_country = "de"
    extract_date = date.today()
    search_roles = [
        "data_engineer",
        "analytics_engineer",
        "ai_engineer",
    ]

    for search_role in search_roles:
        file_path = (
            Path("data/raw/adzuna")
            / f"country={search_country}"
            / f"search_role={search_role}"
            / f"date={extract_date.isoformat()}"
            / "jobs.jsonl"
        )

        print(f"\nStarting load for role: {search_role}")
        run_load(
            file_path=file_path,
            search_role=search_role,
            search_country=search_country,
            extract_date=extract_date,
        )
