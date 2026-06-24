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

job_skills as (

    select
        source,
        job_id,
        skill,
        category

    from {{ ref('int_job_posting_skills') }}

),

posting_groups as (

    select
        source,
        job_id,
        posting_group_id

    from {{ ref('int_job_posting_groups') }}

),

skill_demand_daily as (

    select
        md5(
            observations.source || '|' ||
            observations.extract_date::text || '|' ||
            observations.search_country || '|' ||
            observations.search_role || '|' ||
            job_skills.skill
        ) as skill_demand_daily_id,
        observations.source,
        observations.extract_date,
        observations.search_country,
        observations.search_role,
        job_skills.skill,
        job_skills.category,
        count(distinct observations.job_id) as posting_count,
        count(distinct posting_groups.posting_group_id) as deduped_posting_group_count

    from observations
    inner join job_skills
        on observations.source = job_skills.source
        and observations.job_id = job_skills.job_id

    left join posting_groups
        on observations.source = posting_groups.source
        and observations.job_id = posting_groups.job_id

    group by
        observations.source,
        observations.extract_date,
        observations.search_country,
        observations.search_role,
        job_skills.skill,
        job_skills.category

)

select *
from skill_demand_daily