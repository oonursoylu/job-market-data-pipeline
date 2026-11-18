{{ config(materialized='table') }}

-- One row per segment and date with observations. Reporting tools use it for the rule
-- that a date counts only when every selected segment was collected. It has no link to
-- skills, so a skill filter cannot change which dates are included.
select
    segment_id || '|' || extract_date::text as segment_date_id,
    segment_id,
    search_country,
    search_role,
    extract_date,
    count(distinct job_posting_key) as observed_postings,
    count(distinct posting_group_id) as observed_groups

from {{ ref('fct_job_observations') }}

group by
    segment_id,
    search_country,
    search_role,
    extract_date
