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