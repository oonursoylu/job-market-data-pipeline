{{ config(severity='warn') }}

-- The raw table no longer rejects a minimum salary above the maximum, because raw data
-- should arrive unchanged and one odd value should not stop a whole load. This warns instead.
select
    source,
    job_id,
    salary_min,
    salary_max

from {{ source('raw', 'job_postings') }}

where salary_min > salary_max
