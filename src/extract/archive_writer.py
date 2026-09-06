from datetime import date
import json
import os
import tempfile
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

    if archive_path.exists():
        raise FileExistsError(f"Archive already exists; refusing to overwrite: {archive_path}")

    # Write completely before publishing. A hard link fails if the target exists.
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=archive_path.parent,
            prefix=".jobs-", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = Path(file.name)
            for job in jobs:
                file.write(json.dumps(job, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())

        os.link(temporary_path, archive_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

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