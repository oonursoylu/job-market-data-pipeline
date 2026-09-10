-- raw.job_postings basic quality checks
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE job_id IS NULL) AS null_job_id,
    COUNT(*) FILTER (WHERE source IS NULL) AS null_source,
    COUNT(*) FILTER (WHERE raw_json IS NULL) AS null_raw_json,
    COUNT(*) FILTER (
        WHERE salary_min IS NOT NULL
          AND salary_max IS NOT NULL
          AND salary_min > salary_max
    ) AS invalid_salary_range
FROM raw.job_postings;

-- field coverage and source limitations (raw values are never imputed here)
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(job_title), '') IS NULL) AS missing_job_title,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(company_name), '') IS NULL) AS missing_company_name,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(location), '') IS NULL) AS missing_location,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(description), '') IS NULL) AS missing_description,
    COUNT(*) FILTER (WHERE CHAR_LENGTH(description) >= 500) AS descriptions_at_or_above_500_chars,
    COUNT(*) FILTER (
        WHERE COALESCE(salary_min > 0, FALSE)
           OR COALESCE(salary_max > 0, FALSE)
    ) AS rows_with_usable_salary,
    COUNT(*) FILTER (
        WHERE COALESCE(salary_min <= 0, FALSE)
           OR COALESCE(salary_max <= 0, FALSE)
    ) AS rows_with_non_positive_salary_bound,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(currency), '') IS NULL) AS missing_source_currency,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM(contract_type), '') IS NULL) AS missing_contract_type
FROM raw.job_postings;

-- age is a quality signal, not proof that an advert is closed
SELECT
    COUNT(*) AS latest_catalog_rows,
    COUNT(*) FILTER (WHERE extract_date - created_at::date > 90) AS first_seen_over_90_days_old,
    COUNT(*) FILTER (WHERE extract_date - created_at::date > 365) AS first_seen_over_one_year_old,
    COUNT(*) FILTER (WHERE created_at::date > extract_date + 1) AS implausible_future_source_dates
FROM raw.job_postings;

-- raw.job_posting_observations quality checks
WITH duplicate_observations AS (
    SELECT COUNT(*) AS duplicate_groups
    FROM (
        SELECT
            source,
            job_id,
            search_country,
            search_role,
            extract_date,
            COUNT(*) AS row_count
        FROM raw.job_posting_observations
        GROUP BY source, job_id, search_country, search_role, extract_date
        HAVING COUNT(*) > 1
    ) duplicates
),
orphan_observations AS (
    SELECT COUNT(*) AS orphan_rows
    FROM raw.job_posting_observations obs
    LEFT JOIN raw.job_postings jobs
        ON obs.source = jobs.source
       AND obs.job_id = jobs.job_id
    WHERE jobs.id IS NULL
)
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE source IS NULL) AS null_source,
    COUNT(*) FILTER (WHERE job_id IS NULL) AS null_job_id,
    COUNT(*) FILTER (WHERE search_role IS NULL) AS null_search_role,
    COUNT(*) FILTER (WHERE search_country IS NULL) AS null_search_country,
    COUNT(*) FILTER (WHERE extract_date IS NULL) AS null_extract_date,
    (SELECT orphan_rows FROM orphan_observations) AS orphan_rows,
    (SELECT duplicate_groups FROM duplicate_observations) AS duplicate_groups
FROM raw.job_posting_observations;

-- observation counts by role and extract date
SELECT
    search_role,
    extract_date,
    COUNT(*) AS observation_count
FROM raw.job_posting_observations
GROUP BY search_role, extract_date
ORDER BY extract_date, search_role;
