import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone

from adzuna_client import (
    DESCRIPTION_CONTRACT,
    DESCRIPTION_TRUNCATION_BOUNDARY,
    SEARCH_ROLES,
    fetch_jobs,
)
from archive_writer import build_archive_path, write_jobs_to_jsonl


def run_extract(country: str, search_role: str, max_pages: int = 2, results_per_page: int = 50) -> None:
    if max_pages < 1 or results_per_page < 1:
        raise ValueError("Page limits must be positive.")
    extract_date = date.today()
    archive_path = build_archive_path(country, search_role, extract_date)
    status_path = archive_path.with_name("extraction_status.json")
    if archive_path.exists() or status_path.exists():
        raise FileExistsError(f"Existing archive or extraction status; review before retrying: {archive_path.parent}")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    status = {
        "version": 2, "status": "in_progress", "country": country,
        "search_role": search_role, "extract_date": extract_date.isoformat(),
        "requested_pages": max_pages, "results_per_page": results_per_page,
        "description_contract": DESCRIPTION_CONTRACT,
        "description_truncation_boundary": DESCRIPTION_TRUNCATION_BOUNDARY,
        "pages": [], "started_at": datetime.now(timezone.utc).isoformat(),
    }
    # Claim this segment before sending requests; never overwrite another run.
    with status_path.open("x", encoding="utf-8") as file:
        json.dump(status, file, indent=2)

    def save_status():
        temporary = status_path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(status, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, status_path)

    all_jobs = []
    try:
        for page in range(1, max_pages + 1):
            data = fetch_jobs(country=country, search_role=search_role,
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
                      sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                      finished_at=datetime.now(timezone.utc).isoformat())
        save_status()
        print(f"Extraction complete: {country}/{search_role}, {len(all_jobs)} records.")
        print(f"Wrote archive file: {archive_path}")
    except Exception as exc:
        status["status"] = "failed"
        # Do not store API URLs or credentials from exception messages.
        status["error_type"] = type(exc).__name__
        save_status()
        raise


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Collect selected job search segments.")
    parser.add_argument("--roles", nargs="+", choices=list(SEARCH_ROLES),
                        default=["data_engineer", "analytics_engineer", "ai_engineer"],
                        help="Search roles to collect. Data Analyst is opt-in during archive-only collection.")
    parser.add_argument("--countries", nargs="+", choices=["de", "gb"], default=["de", "gb"])
    args = parser.parse_args(argv)
    countries = list(dict.fromkeys(args.countries))
    roles = list(dict.fromkeys(args.roles))
    # Check every selected segment before making any API requests.
    for country in countries:
        for role in roles:
            path = build_archive_path(country, role)
            if path.exists() or path.with_name("extraction_status.json").exists():
                raise FileExistsError(f"Existing archive or status; review before retrying: {path.parent}")
    for country in countries:
        for role in roles:
            print(f"\nStarting extract for country: {country}, role: {role}")
            run_extract(country, role, max_pages=3, results_per_page=50)


if __name__ == "__main__":
    main()
