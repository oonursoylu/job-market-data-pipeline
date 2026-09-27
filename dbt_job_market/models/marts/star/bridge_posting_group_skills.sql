{{ config(materialized='table') }}

-- Members of a posting group share normalised title and description text, so they
-- match the same skills. assert_group_members_share_skill_matches checks this.
with job_skills as (

    select
        source,
        job_id,
        skill

    from {{ ref('int_job_posting_skills') }}

),

posting_groups as (

    select
        source,
        job_id,
        posting_group_id

    from {{ ref('int_job_posting_groups') }}

)

select distinct
    md5(posting_groups.posting_group_id || '|' || job_skills.skill) as posting_group_skill_id,
    posting_groups.posting_group_id,
    job_skills.skill

from job_skills
inner join posting_groups
    on job_skills.source = posting_groups.source
    and job_skills.job_id = posting_groups.job_id
