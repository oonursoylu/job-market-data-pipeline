{{ config(materialized='table') }}

-- One row per analytical group, so BI tools can relate fct_job_observations and
-- bridge_posting_group_skills through a unique key. Source and country are part of
-- the group key, so grouping by them cannot split a group; the unique test checks it.
with posting_groups as (

    select
        posting_group_id,
        source,
        search_country,
        company_name,
        company_name_was_missing,
        job_title,
        location,
        extract_date

    from {{ ref('int_job_posting_groups') }}

)

select
    posting_group_id,
    source,
    search_country,
    -- Members share the normalised company and title, so any member's text will do.
    min(company_name) as company_name,
    bool_or(company_name_was_missing) as company_name_was_missing,
    min(job_title) as job_title,
    count(*) as member_posting_count,
    count(distinct location) as location_count,
    min(extract_date) as first_catalog_date

from posting_groups

group by
    posting_group_id,
    source,
    search_country
