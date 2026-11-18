import json
import os
import tempfile
from datetime import date
from pathlib import Path

from src.config import archive_path as build_archive_path


def write_jobs_to_jsonl(jobs: list[dict], country: str, search_role: str, extract_date: date) -> Path:
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
