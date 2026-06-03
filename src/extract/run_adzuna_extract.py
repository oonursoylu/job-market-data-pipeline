from adzuna_client import fetch_jobs
from archive_writer import write_jobs_to_jsonl


def run_extract(country: str, search_role: str, page: int = 1, results_per_page: int = 5) -> None:
    data = fetch_jobs(
        country=country,
        search_role=search_role,
        page=page,
        results_per_page=results_per_page,
    )

    jobs = data.get("results", [])
    archive_path = write_jobs_to_jsonl(
        jobs=jobs,
        country=country,
        search_role=search_role,
    )

    print(f"Search role: {search_role}")
    print(f"Total matching jobs reported by API: {data.get('count')}")
    print(f"Jobs returned in this request: {len(jobs)}")
    print(f"Wrote archive file: {archive_path}")


if __name__ == "__main__":
    run_extract(
        country="de",
        search_role="data_engineer",
        page=1,
        results_per_page=5,
    )