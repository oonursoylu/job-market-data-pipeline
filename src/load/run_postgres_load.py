import argparse
import hashlib
import json

from datetime import date
from pathlib import Path

from job_mapper import map_adzuna_job
from jsonl_reader import read_jsonl
from postgres_loader import insert_job_posting_observations, insert_job_postings


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
    observation_inserted_count = insert_job_posting_observations(mapped_jobs)
    observation_duplicate_count = len(mapped_jobs) - observation_inserted_count

    print(f"Read records: {len(raw_jobs)}")
    print(f"Mapped records: {len(mapped_jobs)}")
    print(f"Inserted records: {inserted_count}")
    print(f"Skipped duplicates: {duplicate_count}")
    print(f"Inserted observations: {observation_inserted_count}")
    print(f"Skipped duplicate observations: {observation_duplicate_count}")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a valid date in YYYY-MM-DD format.") from exc


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Load an existing daily job archive.")
    parser.add_argument("--date", type=parse_date, default=date.today(), dest="extract_date",
                        help="Archive date in YYYY-MM-DD format (default: today).")
    parser.add_argument("--check-only", action="store_true",
                        help="Validate all expected archives without writing to PostgreSQL.")
    args = parser.parse_args(argv)

    countries = ["de", "gb"]
    roles = ["data_engineer", "analytics_engineer", "ai_engineer"]
    batch = [
        (country, role, Path("data/raw/adzuna") / f"country={country}"
         / f"search_role={role}" / f"date={args.extract_date.isoformat()}" / "jobs.jsonl")
        for country in countries for role in roles
    ]

    missing = [str(path) for _, _, path in batch if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing archives; no database writes performed:\n" + "\n".join(missing))

    # Validate every file before loading any segment.
    total_rows = 0
    for country, role, path in batch:
        try:
            records = read_jsonl(path)
        except (ValueError, OSError) as exc:
            raise ValueError(f"Cannot read archive: {path}. No database writes performed.") from exc
        for line_number, record in enumerate(records, start=1):
            if not isinstance(record, dict) or not record.get("id"):
                raise ValueError(f"Invalid record {line_number} in {path}: expected an object with an id.")
        status_path = path.with_name("extraction_status.json")
        if status_path.exists():
            status = json.loads(status_path.read_text(encoding="utf-8"))
            pages = status.get("pages", [])
            requested = status.get("requested_pages")
            valid = (
                status.get("version") == 1
                and status.get("status") == "complete"
                and status.get("country") == country
                and status.get("search_role") == role
                and status.get("extract_date") == args.extract_date.isoformat()
                and isinstance(requested, int) and requested > 0
                and isinstance(pages, list)
                and all(isinstance(item, dict) and isinstance(item.get("records"), int)
                        and item["records"] >= 0 for item in pages)
                and [item.get("page") for item in pages] == list(range(1, requested + 1))
                and sum(item["records"] for item in pages) == len(records)
                and status.get("total_records") == len(records)
                and status.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest()
            )
            if not valid:
                raise ValueError(f"Incomplete or inconsistent extraction status: {status_path}")
            print(f"Verified extraction: {country}/{role}, {requested} pages")
        else:
            print(f"Warning: no extraction status for {country}/{role}; page completion is unverified.")
        total_rows += len(records)
        print(f"Validated {country}/{role}: {len(records)} records")
        if not records:
            print(f"Warning: empty archive for {country}/{role}; check extraction results.")

    print(f"Archive check passed: {len(batch)} files, {total_rows} records, date {args.extract_date}.")
    if args.check_only:
        print("Check only: no database writes performed.")
        return

    for country, role, path in batch:
        print(f"\nStarting load for country: {country}, role: {role}")
        run_load(path, role, country, args.extract_date)


if __name__ == "__main__":
    main()
