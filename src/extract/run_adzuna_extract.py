from adzuna_client import fetch_jobs
from archive_writer import write_jobs_to_jsonl


def run_extract(country: str, search_role: str, max_pages: int = 2, results_per_page: int = 50) -> None:
    all_jobs = []
    total_matching_jobs = None

    for page in range(1, max_pages + 1):
        data = fetch_jobs(
            country=country,
            search_role=search_role,
            page=page,
            results_per_page=results_per_page,
        )

        if total_matching_jobs is None:
            total_matching_jobs = data.get("count")

        jobs = data.get("results", [])
        all_jobs.extend(jobs)

        print(f"Page {page}: fetched {len(jobs)} jobs")

    archive_path = write_jobs_to_jsonl(
        jobs=all_jobs,
        country=country,
        search_role=search_role,
    )

    print(f"Search role: {search_role}")
    print(f"Total matching jobs reported by API: {total_matching_jobs}")
    print(f"Total jobs fetched in this run: {len(all_jobs)}")
    print(f"Wrote archive file: {archive_path}")


if __name__ == "__main__":
    search_roles = [
        "data_engineer",
        "analytics_engineer",
        "ai_engineer",
    ]

    for search_role in search_roles:
        print(f"\nStarting extract for role: {search_role}")
        run_extract(
            country="de",
            search_role=search_role,
            max_pages=2,
            results_per_page=50,
        )
