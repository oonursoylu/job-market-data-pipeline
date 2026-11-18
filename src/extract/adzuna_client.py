import os

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import PROJECT_ROOT


BASE_URL = "https://api.adzuna.com/v1/api/jobs"
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)


class AdzunaRequestError(RuntimeError):
    """A failed API request. The message never contains the request URL,
    because the URL carries the app_id and app_key."""


def build_session(retries: int = 4, backoff_factor: float = 2.0) -> requests.Session:
    """Session that retries rate limits and server errors with growing waits."""
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def load_credentials() -> tuple[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise ValueError("Missing ADZUNA_APP_ID or ADZUNA_APP_KEY in .env")
    return app_id, app_key


def fetch_jobs(
    session: requests.Session,
    credentials: tuple[str, str],
    country: str,
    search_term: str,
    page: int = 1,
    results_per_page: int = 50,
) -> dict:
    app_id, app_key = credentials
    url = f"{BASE_URL}/{country}/search/{page}"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": search_term,
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }
    where = f"{country} '{search_term}' page {page}"
    try:
        response = session.get(url, params=params, timeout=20)
    except requests.RequestException as exc:
        # requests puts the full URL in its messages; report only the error type.
        raise AdzunaRequestError(f"Request failed for {where}: {type(exc).__name__}") from None
    if response.status_code != 200:
        raise AdzunaRequestError(f"Adzuna returned HTTP {response.status_code} for {where}")
    try:
        return response.json()
    except ValueError:
        raise AdzunaRequestError(f"Adzuna returned invalid JSON for {where}") from None


if __name__ == "__main__":
    data = fetch_jobs(build_session(), load_credentials(), "de", "data engineer", results_per_page=5)
    results = data.get("results", [])
    print(f"Total matching jobs reported by API: {data.get('count')}")
    print(f"Jobs returned in this request: {len(results)}")
    if results:
        print(f"First job id: {results[0].get('id')}")
        print(f"First job title: {results[0].get('title')}")
