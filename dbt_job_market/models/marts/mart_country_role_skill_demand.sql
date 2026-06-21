{{ config(materialized='table') }}

with skill_demand_daily as (

    select
        source,
        extract_date,
        search_country,
        search_role,
        skill,
        category,
        posting_count

    from {{ ref('fct_skill_demand_daily') }}

),

country_role_skill_demand as (

    select
        md5(
            source || '|' ||
            search_country || '|' ||
            search_role || '|' ||
            skill
        ) as country_role_skill_demand_id,
        source,
        search_country,
        search_role,
        skill,
        category,
        sum(posting_count) as total_skill_mentions,
        count(distinct extract_date) as active_run_days,
        round(avg(posting_count)::numeric, 2) as avg_skill_mentions_per_run,
        max(extract_date) as latest_extract_date

    from skill_demand_daily

    group by
        source,
        search_country,
        search_role,
        skill,
        category

)

select *
from country_role_skill_demand