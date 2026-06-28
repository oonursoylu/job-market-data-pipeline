{{ config(materialized='table') }}

with skill_demand as (

    select
        source,
        search_country,
        search_role,
        skill,
        category,
        deduped_total_skill_mentions,
        active_run_days,
        deduped_avg_skill_mentions_per_run,
        latest_extract_date

    from {{ ref('mart_country_role_skill_demand') }}

),

dashboard_skill_demand as (

    select
        md5(
            source || '|' ||
            search_country || '|' ||
            search_role || '|' ||
            skill
        ) as skill_demand_dashboard_id,
        source,
        search_country,
        search_role,
        skill,
        category,
        deduped_total_skill_mentions as total_skill_mentions,
        active_run_days,
        deduped_avg_skill_mentions_per_run as avg_skill_mentions_per_run,
        latest_extract_date

    from skill_demand

)

select *
from dashboard_skill_demand