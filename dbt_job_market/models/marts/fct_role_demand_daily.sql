{{ config(materialized='table') }}

with observations as (

    select
        source,
        job_id,
        search_country,
        search_role,
        extract_date

    from {{ ref('stg_job_posting_observations') }}

),

posting_groups as (

    select
        source,
        job_id,
        posting_group_id

    from {{ ref('int_job_posting_groups') }}

),

role_demand_daily as (

    select
        md5(
            observations.source || '|' ||
            observations.extract_date::text || '|' ||
            observations.search_country || '|' ||
            observations.search_role
        ) as role_demand_daily_id,
        observations.source,
        observations.extract_date,
        observations.search_country,
        observations.search_role,
        count(distinct observations.job_id) as observed_posting_count,
        count(distinct posting_groups.posting_group_id) as deduped_posting_group_count

    from observations
    left join posting_groups
        on observations.source = posting_groups.source
        and observations.job_id = posting_groups.job_id

    group by
        observations.source,
        observations.extract_date,
        observations.search_country,
        observations.search_role

)

select *
from role_demand_daily