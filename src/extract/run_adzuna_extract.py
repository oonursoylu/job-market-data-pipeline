import argparse
import hashlib
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import (
    COUNTRY_CODES,
    DESCRIPTION_CONTRACT,
    DESCRIPTION_TRUNCATION_BOUNDARY,
    MAX_PAGES,
    REQUEST_PAUSE_SECONDS,
    RESULTS_PER_PAGE,
    ROLE_CODES,
    SEARCH_TERMS,
    archive_path,
    expected_segments,
    status_path,
)
from src.extract.adzuna_client import build_session, fetch_jobs, load_credentials
from src.extract.archive_writer import write_jobs_to_jsonl


def read_status(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def segment_state(country: str, role: str, extract_date: date) -> str:
    """Return 'new', 'complete', 'failed' (safe to retry) or 'blocked' (needs review)."""
    archive = archive_path(country, role, extract_date)
    status_file = status_path(country, role, extract_date)
    if not archive.exists() and not status_file.exists():
        return "new"
    status = read_status(status_file) if status_file.exists() else None
    if archive.exists() and (not status_file.exists() or (status or {}).get("status") == "complete"):
        return "complete"
    if not archive.exists() and (status or {}).get("status") == "failed":
        return "failed"
    return "blocked"


def plan_segments(extract_date: date, countries, roles, resume: bool) -> list[tuple[str, str]]:
    """Check every selected segment before any API request is sent."""
    to_run, blocked = [], []
    for country, role in expected_segments(extract_date, countries, roles):
        state = segment_state(country, role, extract_date)
        if state == "new" or (resume and state == "failed"):
            to_run.append((country, role))
        elif resume and state == "complete":
            print(f"Already complete, skipping: {country}/{role}")
        else:
            blocked.append(f"{country}/{role} ({state})")
    if blocked:
        raise FileExistsError(
            "Existing archive or extraction status; review before retrying: " + ", ".join(blocked)
        )
    return to_run


def set_aside_failed_status(country: str, role: str, extract_date: date) -> None:
    """Keep the failed status for the record and free the name for a new attempt."""
    status_file = status_path(country, role, extract_date)
    if status_file.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        status_file.rename(status_file.with_name(f"extraction_status.failed-{stamp}.json"))


def run_extract(
    session,
    credentials,
    country: str,
    search_role: str,
    extract_date: date,
    max_pages: int = MAX_PAGES,
    results_per_page: int = RESULTS_PER_PAGE,
    pause_seconds: float = REQUEST_PAUSE_SECONDS,
) -> int:
    if max_pages < 1 or results_per_page < 1:
        raise ValueError("Page limits must be positive.")
    archive = archive_path(country, search_role, extract_date)
    status_file = status_path(country, search_role, extract_date)
    archive.parent.mkdir(parents=True, exist_ok=True)
    status = {
        "version": 2, "status": "in_progress", "country": country,
        "search_role": search_role, "extract_date": extract_date.isoformat(),
        "requested_pages": max_pages, "results_per_page": results_per_page,
        "description_contract": DESCRIPTION_CONTRACT,
        "description_truncation_boundary": DESCRIPTION_TRUNCATION_BOUNDARY,
        "pages": [], "started_at": datetime.now(timezone.utc).isoformat(),
    }
    # Claim this segment before sending requests; never overwrite another run.
    with status_file.open("x", encoding="utf-8") as file:
        json.dump(status, file, indent=2)

    def save_status():
        temporary = status_file.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(status, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, status_file)

    all_jobs = []
    try:
        for page in range(1, max_pages + 1):
            if pause_seconds:
                time.sleep(pause_seconds)  # stay well inside the API's per-minute limit
            data = fetch_jobs(session, credentials, country, SEARCH_TERMS[search_role],
                              page=page, results_per_page=results_per_page)
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise ValueError("Invalid API response: expected a results list.")
            jobs = data["results"]
            if any(not isinstance(job, dict) or not job.get("id") for job in jobs):
                raise ValueError("Invalid API record: missing job id.")
            all_jobs.extend(jobs)
            status["pages"].append({"page": page, "records": len(jobs)})
            save_status()
            print(f"Page {page}: fetched {len(jobs)} jobs")

        write_jobs_to_jsonl(all_jobs, country, search_role, extract_date)
        description_lengths = [
            len(job["description"])
            for job in all_jobs
            if isinstance(job.get("description"), str)
        ]
        status.update(status="complete", total_records=len(all_jobs),
                      description_profile={
                          "records_with_description": len(description_lengths),
                          "records_at_or_above_boundary": sum(
                              length >= DESCRIPTION_TRUNCATION_BOUNDARY
                              for length in description_lengths
                          ),
                          "maximum_characters": max(description_lengths, default=0),
                      },
                      sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                      finished_at=datetime.now(timezone.utc).isoformat())
        save_status()
        print(f"Extraction complete: {country}/{search_role}, {len(all_jobs)} records.")
        return len(all_jobs)
    except Exception as exc:
        status["status"] = "failed"
        # Do not store API URLs or credentials from exception messages.
        status["error_type"] = type(exc).__name__
        save_status()
        raise


def extract_all(extract_date: date, countries=None, roles=None, resume: bool = False) -> int:
    """Collect every selected segment for a date. Returns the number of records fetched."""
    segments = plan_segments(extract_date, countries, roles, resume)
    if not segments:
        print("Nothing to collect: every selected segment is already complete.")
        return 0
    session, credentials = build_session(), load_credentials()
    total = 0
    for country, role in segments:
        print(f"\nStarting extract for country: {country}, role: {role}")
        if resume:
            set_aside_failed_status(country, role, extract_date)
        total += run_extract(session, credentials, country, role, extract_date)
    return total


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Collect today's job search segments from Adzuna.")
    parser.add_argument("--roles", nargs="+", choices=ROLE_CODES, default=ROLE_CODES,
                        help="Search roles to collect (default: all).")
    parser.add_argument("--countries", nargs="+", choices=COUNTRY_CODES, default=COUNTRY_CODES,
                        help="Countries to collect (default: all).")
    parser.add_argument("--resume", action="store_true",
                        help="Skip segments already complete today and retry failed ones.")
    args = parser.parse_args(argv)
    extract_all(date.today(), list(dict.fromkeys(args.countries)), list(dict.fromkeys(args.roles)), args.resume)


if __name__ == "__main__":
    main()
