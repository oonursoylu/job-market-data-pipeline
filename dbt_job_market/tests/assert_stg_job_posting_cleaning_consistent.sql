select
    postings.source,
    postings.job_id
from {{ ref('stg_job_postings') }} as postings
left join {{ ref('search_countries') }} as countries
    on postings.search_country = countries.search_country
where
    (company_name_was_missing and company_name <> 'Unknown')
    or salary_is_available is distinct from (salary_min is not null or salary_max is not null)
    or salary_range_is_complete is distinct from (salary_min is not null and salary_max is not null)
    or coalesce(salary_min <= 0, false)
    or coalesce(salary_max <= 0, false)
    or (salary_is_available and currency is null)
    or (not salary_is_available and currency is not null)
    or salary_currency_was_inferred is distinct from (
        salary_is_available
        and source_currency is null
        and countries.salary_currency is not null
    )
    or (
        salary_is_available
        and source_currency is not null
        and currency is distinct from source_currency
    )
    or (
        salary_is_available
        and source_currency is null
        and currency is distinct from countries.salary_currency
    )
    or description_is_source_snippet is distinct from (postings.source = 'adzuna')
    or description_length is distinct from char_length(raw_json ->> 'description')
    or description_is_likely_truncated is distinct from (
        postings.source = 'adzuna' and coalesce(description_length, 0) >= 500
    )
