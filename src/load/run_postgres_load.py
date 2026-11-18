import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from src import config
from src.config import CATCH_UP_DAYS, COUNTRY_CODES, ROLE_CODES, archive_path, expected_segments, status_path
from src.load.job_mapper import map_adzuna_job
from src.load.jsonl_reader import read_jsonl
from src.load.postgres_loader import get_connection, load_segment


def description_profile(records: list[dict], boundary: int) -> dict:
    lengths = [len(record["description"]) for record in records if isinstance(record.get("description"), str)]
    return {
        "records_with_description": len(lengths),
        "records_at_or_above_boundary": sum(length >= boundary for length in lengths),
        "maximum_characters": max(lengths, default=0),
    }


def status_is_valid(status: dict, path: Path, records: list[dict], country: str, role: str,
                    extract_date: date) -> bool:
    version = status.get("version")
    pages = status.get("pages", [])
    requested = status.get("requested_pages")
    boundary = status.get("description_truncation_boundary")
    has_valid_boundary = isinstance(boundary, int) and boundary > 0
    total_count = status.get("api_total_count")
    return (
        version in (1, 2, 3)
        and status.get("status") == "complete"
        and status.get("country") == country
        and status.get("search_role") == role
        and status.get("extract_date") == extract_date.isoformat()
        and isinstance(requested, int) and requested > 0
        and isinstance(pages, list)
        and all(isinstance(item, dict) and isinstance(item.get("records"), int)
                and item["records"] >= 0 for item in pages)
        and [item.get("page") for item in pages] == list(range(1, requested + 1))
        and sum(item["records"] for item in pages) == len(records)
        and status.get("total_records") == len(records)
        and status.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest()
        # Version 3 also records the API's total match count, which may be missing (null).
        and (version < 3 or total_count is None or (isinstance(total_count, int) and total_count >= 0))
        and (
            version == 1
            or (
                status.get("description_contract") == "snippet"
                and has_valid_boundary
                and status.get("description_profile")
                == description_profile(records, boundary if has_valid_boundary else 500)
            )
        )
    )


def validate_archive(country: str, role: str, extract_date: date) -> list[dict]:
    """Read one archive and check it against its extraction status. Returns the records."""
    path = archive_path(country, role, extract_date)
    try:
        records = read_jsonl(path)
    except (ValueError, OSError) as exc:
        raise ValueError(f"Cannot read archive: {path}. No database writes performed.") from exc
    for line_number, record in enumerate(records, start=1):
        if not isinstance(record, dict) or not record.get("id"):
            raise ValueError(f"Invalid record {line_number} in {path}: expected an object with an id.")
        if record.get("description") is not None and not isinstance(record["description"], str):
            raise ValueError(f"Invalid record {line_number} in {path}: description must be text or null.")

    status_file = status_path(country, role, extract_date)
    if status_file.exists():
        status = json.loads(status_file.read_text(encoding="utf-8"))
        if not status_is_valid(status, path, records, country, role, extract_date):
            raise ValueError(f"Incomplete or inconsistent extraction status: {status_file}")
        print(f"Verified extraction: {country}/{role}, {status['requested_pages']} pages")
    else:
        print(f"Warning: no extraction status for {country}/{role}; page completion is unverified.")
    print(f"Validated {country}/{role}: {len(records)} records")
    if not records:
        print(f"Warning: empty archive for {country}/{role}; check extraction results.")
    return records


def run_load(connection, raw_jobs: list[dict], search_role: str, search_country: str, extract_date: date) -> tuple[int, int]:
    mapped_jobs = [
        map_adzuna_job(job=job, search_role=search_role, search_country=search_country, extract_date=extract_date)
        for job in raw_jobs
    ]
    inserted_count, observation_inserted_count = load_segment(connection, mapped_jobs)

    print(f"Read records: {len(raw_jobs)}")
    print(f"Inserted records: {inserted_count}")
    print(f"Skipped duplicates: {len(mapped_jobs) - inserted_count}")
    print(f"Inserted observations: {observation_inserted_count}")
    print(f"Skipped duplicate observations: {len(mapped_jobs) - observation_inserted_count}")
    return inserted_count, observation_inserted_count


def load_date(extract_date: date, countries=None, roles=None, check_only: bool = False) -> tuple[int, int]:
    """Validate every expected archive for a date, then load each segment in its own transaction."""
    segments = expected_segments(extract_date, countries, roles)
    if not segments:
        raise ValueError(f"No segments were collected on {extract_date}.")

    missing = [str(archive_path(c, r, extract_date)) for c, r in segments
               if not archive_path(c, r, extract_date).is_file()]
    if missing:
        raise FileNotFoundError("Missing archives; no database writes performed:\n" + "\n".join(missing))

    # Validate every file before loading any segment, and load exactly the records that were checked.
    validated = [(country, role, validate_archive(country, role, extract_date)) for country, role in segments]
    total_rows = sum(len(records) for _, _, records in validated)
    print(f"Archive check passed: {len(validated)} files, {total_rows} records, date {extract_date}.")
    if check_only:
        print("Check only: no database writes performed.")
        return 0, 0

    postings = observations = 0
    connection = get_connection()
    try:
        for country, role, records in validated:
            print(f"\nStarting load for country: {country}, role: {role}")
            inserted, observed = run_load(connection, records, role, country, extract_date)
            postings += inserted
            observations += observed
    finally:
        connection.close()
    print(f"\nLoad complete: {postings} new postings, {observations} new observations.")
    return postings, observations


def loaded_segments(connection, since: date) -> set[tuple[date, str, str]]:
    """Date, country and role combinations that already have observations in PostgreSQL."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT extract_date, search_country, search_role
            FROM raw.job_posting_observations
            WHERE extract_date >= %s
            """,
            (since,),
        )
        return set(cursor.fetchall())


def dates_to_catch_up(run_date: date, loaded: set, lookback_days: int = CATCH_UP_DAYS) -> list[date]:
    """Archived days before run_date, inside the look-back window, that are not fully loaded.

    A segment is missing when its archive has records but PostgreSQL has no observation for it
    on that date. An empty archive has nothing to load, so it never counts as missing.
    """
    since = run_date - timedelta(days=lookback_days)
    days = set()
    for folder in config.RAW_DATA_DIR.glob("country=*/search_role=*/date=*"):
        try:
            day = date.fromisoformat(folder.name.split("=", 1)[1])
        except ValueError:
            continue
        if since <= day < run_date:
            days.add(day)

    pending = []
    for day in sorted(days):
        for country, role in expected_segments(day):
            path = archive_path(country, role, day)
            if (day, country, role) not in loaded and path.is_file() and path.stat().st_size > 0:
                pending.append(day)
                break
    return pending


def catch_up(run_date: date, lookback_days: int = CATCH_UP_DAYS) -> list[date]:
    """Load archived days from the look-back window that PostgreSQL does not fully have.

    Returns the days it loaded. A day with a missing or inconsistent archive is reported
    and skipped, so one bad day never blocks the current run.
    """
    connection = get_connection()
    try:
        loaded = loaded_segments(connection, run_date - timedelta(days=lookback_days))
    finally:
        connection.close()

    pending = dates_to_catch_up(run_date, loaded, lookback_days)
    if not pending:
        print(f"No earlier days to catch up (checked the last {lookback_days} days).")
    caught_up = []
    for day in pending:
        print(f"\nCatching up {day}: its archives are on disk but not fully in PostgreSQL.")
        try:
            load_date(day)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Warning: {day} was not loaded and needs a manual look. {exc}")
            continue
        caught_up.append(day)
    return caught_up


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
    # By default the loader expects every segment that was being collected on that date
    # (start dates are in the search_countries and search_roles seeds).
    parser.add_argument("--roles", nargs="+", choices=ROLE_CODES, default=None,
                        help="Roles to load (default: every role collected on that date).")
    parser.add_argument("--countries", nargs="+", choices=COUNTRY_CODES, default=None,
                        help="Countries to load (default: every country collected on that date).")
    args = parser.parse_args(argv)
    countries = list(dict.fromkeys(args.countries)) if args.countries else None
    roles = list(dict.fromkeys(args.roles)) if args.roles else None
    load_date(args.extract_date, countries, roles, args.check_only)


if __name__ == "__main__":
    main()
