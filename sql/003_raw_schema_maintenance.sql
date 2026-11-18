-- Run once on a database created with the earlier 001_create_raw_schema.sql.
-- Safe to run more than once. Takes a moment and changes no data.
--
--   psql -h localhost -U job_market_user -d job_market -f .\sql\003_raw_schema_maintenance.sql

-- Raw rows should arrive unchanged: one posting with a minimum salary above the maximum
-- should not stop a whole segment from loading. dbt now warns about such rows instead
-- (tests/assert_source_salary_range_valid.sql).
ALTER TABLE raw.job_postings
    DROP CONSTRAINT IF EXISTS chk_job_postings_salary_range;

-- Duplicate of the unique constraint's index, which already starts with (source, job_id).
DROP INDEX IF EXISTS raw.idx_job_posting_observations_source_job_id;
