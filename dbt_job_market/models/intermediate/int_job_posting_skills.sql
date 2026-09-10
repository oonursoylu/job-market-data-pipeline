{{ config(materialized='table') }}

with job_postings as (

    select
        source,
        job_id,
        search_country,
        search_role,
        posted_date,
        extract_date,
        ' ' || regexp_replace(
            lower(concat_ws(' ', job_title, description)),
            '[^a-z0-9]+',
            ' ',
            'g'
        ) || ' ' as normalized_search_text

    from {{ ref('stg_job_postings') }}
    where job_title is not null or description is not null

),

skills as (

    select
        skill,
        category,
        lower(pattern) as pattern

    from {{ ref('skill_dictionary') }}

),

matched_skills as (

    select
        md5(job_postings.source || '|' || job_postings.job_id || '|' || skills.skill) as job_skill_id,
        job_postings.source,
        job_postings.job_id,
        job_postings.search_country,
        job_postings.search_role,
        job_postings.posted_date,
        job_postings.extract_date,
        skills.skill,
        skills.category

    from job_postings
    inner join skills
        on exists (
            select 1
            from unnest(string_to_array(skills.pattern, '|')) as aliases(alias)
            where job_postings.normalized_search_text like '% ' || trim(aliases.alias) || ' %'
        )

)

select *
from matched_skills
