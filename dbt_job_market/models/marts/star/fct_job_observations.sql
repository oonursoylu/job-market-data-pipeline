{{ config(materialized='table') }}

-- One row per observation: a posting seen in a country and role search on a date.
-- Counting rules are applied by the consumers on this grain.
with observations as (

    select
        observation_id,
        source,
        job_id,
        search_country,
        search_role,
        extract_date

    from {{ ref('stg_job_posting_observations') }}

),

job_postings as (

    select
        source,
        job_id,
        posted_date

    from {{ ref('stg_job_postings') }}

),

posting_groups as (

    select
        source,
        job_id,
        posting_group_id

    from {{ ref('int_job_posting_groups') }}

)

select
    observations.observation_id,
    md5(observations.source || '|' || observations.job_id) as job_posting_key,
    observations.search_country || '|' || observations.search_role as segment_id,
    posting_groups.posting_group_id,
    observations.source,
    observations.job_id,
    observations.search_country,
    observations.search_role,
    observations.extract_date,
    case
        when job_postings.posted_date is not null
            then greatest(observations.extract_date - job_postings.posted_date, 0)
    end as posting_age_days,
    coalesce(
        observations.extract_date - job_postings.posted_date > 90,
        false
    ) as is_stale_at_observation

from observations
inner join job_postings
    on observations.source = job_postings.source
    and observations.job_id = job_postings.job_id

inner join posting_groups
    on observations.source = posting_groups.source
    and observations.job_id = posting_groups.job_id
