from datetime import date


def map_adzuna_job(job: dict, search_role: str, search_country: str, extract_date: date) -> dict:
    company = job.get("company") or {}
    location = job.get("location") or {}
    category = job.get("category") or {}

    return {
        "source": "adzuna",
        "job_id": job.get("id"),
        "job_title": job.get("title"),
        "company_name": company.get("display_name"),
        "location": location.get("display_name"),
        "country": search_country,
        "description": job.get("description"),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "currency": job.get("salary_currency"),
        "contract_type": job.get("contract_type"),
        "category": category.get("label"),
        "redirect_url": job.get("redirect_url"),
        "created_at": job.get("created"),
        "search_role": search_role,
        "search_country": search_country,
        "raw_json": job,
        "extract_date": extract_date,
    }


if __name__ == "__main__":
    sample_job = {
        "id": "123",
        "title": "Data Engineer",
        "company": {"display_name": "Example GmbH"},
        "location": {"display_name": "Berlin, Germany"},
        "category": {"label": "IT Jobs"},
        "description": "Example description",
        "created": "2026-06-03T10:00:00Z",
        "redirect_url": "https://example.com/job/123",
    }

    mapped = map_adzuna_job(
        job=sample_job,
        search_role="data_engineer",
        search_country="de",
        extract_date=date.today(),
    )

    print(mapped)