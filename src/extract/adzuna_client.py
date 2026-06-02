import os

import requests
from dotenv import load_dotenv


BASE_URL = "https://api.adzuna.com/v1/api/jobs"

SEARCH_ROLES = {
    "data_engineer": "data engineer",
    "analytics_engineer": "analytics engineer",
    "ai_engineer": "ai engineer",
}


def fetch_jobs(country: str, search_role: str, page: int = 1, results_per_page: int = 5) -> dict:
    load_dotenv()

    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        raise ValueError("Missing ADZUNA_APP_ID or ADZUNA_APP_KEY in .env")

    if search_role not in SEARCH_ROLES:
        raise ValueError(f"Unknown search_role: {search_role}")

    url = f"{BASE_URL}/{country}/search/{page}"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": SEARCH_ROLES[search_role],
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    data = fetch_jobs(country="de", search_role="data_engineer", results_per_page=5)
    results = data.get("results", [])

    print(f"Total matching jobs reported by API: {data.get('count')}")
    print(f"Jobs returned in this request: {len(results)}")

    if results:
        first_job = results[0]
        print(f"First job id: {first_job.get('id')}")
        print(f"First job title: {first_job.get('title')}")