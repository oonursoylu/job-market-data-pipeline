"""Invented adverts for CI, written through the real extractor with a fake API.

Run from the repository root:  python -m tests.sample_data

It creates the raw schema in the database named in the environment and writes archives
for two collection days into data/raw/adzuna, so the loader, the catch-up step, dbt and
the dashboard checks all run on data shaped like the real thing. Nothing here comes from
Adzuna: companies, titles and texts are made up.
"""
from datetime import date

from src import config
from src.extract import run_adzuna_extract as extract
from src.load.postgres_loader import get_connection
from tests.conftest import FakeResponse, FakeSession

DAYS = [date(2026, 11, 16), date(2026, 11, 18)]
POOL_SIZE = 24          # adverts per country
PER_SEGMENT = 12        # 3 pages of 4
COMPANIES = ["Northwind Data GmbH", "Contoso Analytics Ltd", "Fabrikam AI", None, "Müller & Söhne KG"]
TITLES = {
    "de": ["Data Engineer (m/w/d)", "Analytics Engineer (m/w/d)", "Werkstudent Data Engineer (m/w/d)",
           "AI Engineer (m/w/d)", "Data Analyst (m/w/d)"],
    "gb": ["Data Engineer", "Analytics Engineer", "Graduate Data Analyst Apprenticeship",
           "AI Engineer", "Senior Data Analyst"],
}
SKILL_TEXT = [
    "We build pipelines with Python, SQL and dbt on Snowflake.",
    "You will model data in Power BI with DAX and Power Query.",
    "Experience with Spark, Kafka and AWS is a plus.",
    "Machine learning, PyTorch and MLflow in production.",
    "Excel and statistics for weekly reporting.",
]
GERMAN_TEXT = " Wir suchen Erfahrung mit Datenqualität und Datenmodellierung."


def advert(country: str, index: int) -> dict:
    # Adverts index and index + 10 share company, title and text but not id or location,
    # so they form one analytical group (unless the company is missing).
    base = index % 10
    company = COMPANIES[base % len(COMPANIES)]
    text = SKILL_TEXT[base % len(SKILL_TEXT)] + (GERMAN_TEXT if country == "de" else "")
    if base == 9:
        text = (text + " " + "Details follow in the full advert. " * 20)[:500]  # snippet boundary
    record = {
        "id": f"{country}{1000 + index}",
        "title": TITLES[country][base % len(TITLES[country])],
        "company": {"display_name": company} if company else {},
        "location": {"display_name": f"City {index}"},
        "description": text,
        "created": "2026-06-01T09:00:00Z" if base % 7 == 0 else "2026-11-01T09:00:00Z",
        "category": {"label": "IT Jobs"},
        "contract_type": "permanent",
        "redirect_url": f"https://example.invalid/jobs/{country}{1000 + index}",
    }
    if base % 3 == 0:
        record.update(salary_min=45000, salary_max=60000, salary_is_predicted="1" if base % 2 else "0")
    elif base == 4:
        record.update(salary_min=0, salary_max=0)  # placeholder bounds, treated as missing
    return record


def segment_pages(country: str, role_number: int, day_number: int) -> list:
    # Roles and days take overlapping windows of the pool, so adverts repeat across roles and days.
    indexes = [(role_number * 3 + day_number * 4 + j) % POOL_SIZE for j in range(PER_SEGMENT)]
    adverts = [advert(country, i) for i in indexes]
    return [FakeResponse(200, {"results": adverts[start:start + 4], "count": 900 + role_number})
            for start in range(0, PER_SEGMENT, 4)]


def main() -> None:
    connection = get_connection()
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute((config.PROJECT_ROOT / "sql" / "001_create_raw_schema.sql").read_text(encoding="utf-8"))
    finally:
        connection.close()

    for day_number, day in enumerate(DAYS):
        for country, role in config.expected_segments(day):
            pages = segment_pages(country, config.ROLE_CODES.index(role), day_number)
            extract.run_extract(FakeSession(pages), ("ci", "ci"), country, role, day,
                                max_pages=3, results_per_page=4, pause_seconds=0)
    print(f"Sample archives written for {', '.join(map(str, DAYS))}.")


if __name__ == "__main__":
    main()
