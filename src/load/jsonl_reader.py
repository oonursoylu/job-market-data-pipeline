import json
from pathlib import Path


def read_jsonl(file_path: str | Path) -> list[dict]:
    path = Path(file_path)
    records = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))

    return records


if __name__ == "__main__":
    sample_path = Path(
        "data/raw/adzuna/country=de/search_role=data_engineer/date=2026-06-03/jobs.jsonl"
    )

    jobs = read_jsonl(sample_path)

    print(f"Read {len(jobs)} jobs from {sample_path}")

    if jobs:
        print(f"First job id: {jobs[0].get('id')}")
        print(f"First job title: {jobs[0].get('title')}")