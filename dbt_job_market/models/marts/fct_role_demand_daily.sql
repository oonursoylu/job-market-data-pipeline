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

role_demand_daily as (

    select
        md5(
            source || '|' ||
            extract_date::text || '|' ||
            search_country || '|' ||
            search_role
        ) as role_demand_daily_id,
        source,
        extract_date,
        search_country,
        search_role,
        count(distinct job_id) as observed_posting_count

    from observations

    group by
        source,
        extract_date,
        search_country,
        search_role

)

select *
from role_demand_daily