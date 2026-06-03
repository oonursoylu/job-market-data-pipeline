from datetime import date
import json
from pathlib import Path


RAW_DATA_DIR = Path("data/raw/adzuna")


def build_archive_path(country: str, search_role: str, extract_date: date | None = None) -> Path:
    if extract_date is None:
        extract_date = date.today()

    return (
        RAW_DATA_DIR
        / f"country={country}"
        / f"search_role={search_role}"
        / f"date={extract_date.isoformat()}"
        / "jobs.jsonl"
    )


def write_jobs_to_jsonl(
    jobs: list[dict],
    country: str,
    search_role: str,
    extract_date: date | None = None,
) -> Path:
    archive_path = build_archive_path(country, search_role, extract_date)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with archive_path.open("w", encoding="utf-8") as file:
        for job in jobs:
            file.write(json.dumps(job, ensure_ascii=False) + "\n")

    return archive_path


if __name__ == "__main__":
    sample_jobs = [
        {"id": "test_1", "title": "Data Engineer"},
        {"id": "test_2", "title": "Analytics Engineer"},
    ]

    path = write_jobs_to_jsonl(
        jobs=sample_jobs,
        country="de",
        search_role="data_engineer",
    )

    print(f"Wrote {len(sample_jobs)} jobs to {path}")