{{ config(materialized='table') }}

with job_postings as (

    select
        source,
        job_id,
        job_title,
        company_name,
        location,
        country,
        posted_date,
        redirect_url

    from {{ ref('stg_job_postings') }}

),

observations as (

    select
        source,
        job_id,
        search_country,
        search_role,
        extract_date,
        observed_at

    from {{ ref('stg_job_posting_observations') }}

),

observation_summary as (

    select
        source,
        job_id,
        min(extract_date) as first_observed_date,
        max(extract_date) as latest_extract_date,
        count(distinct extract_date) as times_observed

    from observations

    group by
        source,
        job_id

),

latest_observation as (

    select
        source,
        job_id,
        search_country,
        search_role,
        extract_date

    from (
        select
            source,
            job_id,
            search_country,
            search_role,
            extract_date,
            row_number() over (
                partition by source, job_id
                order by extract_date desc, observed_at desc, search_country, search_role
            ) as row_number

        from observations
    ) ranked_observations

    where row_number = 1

),

latest_postings as (

    select
        md5(job_postings.source || '|' || job_postings.job_id) as latest_posting_id,
        job_postings.source,
        job_postings.job_id,
        job_postings.job_title,
        job_postings.company_name,
        job_postings.location,
        job_postings.country,
        latest_observation.search_country,
        latest_observation.search_role,
        job_postings.posted_date,
        observation_summary.first_observed_date,
        observation_summary.latest_extract_date,
        observation_summary.times_observed,
        job_postings.redirect_url

    from job_postings
    inner join observation_summary
        on job_postings.source = observation_summary.source
        and job_postings.job_id = observation_summary.job_id

    inner join latest_observation
        on job_postings.source = latest_observation.source
        and job_postings.job_id = latest_observation.job_id

)

select *
from latest_postings