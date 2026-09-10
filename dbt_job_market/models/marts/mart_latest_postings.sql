{{ config(materialized='table') }}

with job_postings as (

    select
        source,
        job_id,
        job_title,
        company_name,
        company_name_was_missing,
        location,
        country,
        is_training_or_placement,
        description_length,
        description_is_source_snippet,
        description_is_likely_truncated,
        salary_min,
        salary_max,
        salary_is_available,
        salary_range_is_complete,
        currency,
        salary_currency_was_inferred,
        salary_is_predicted,
        contract_type,
        posted_date,
        redirect_url

    from {{ ref('stg_job_postings') }}

),

posting_groups as (

    select
        source,
        job_id,
        posting_group_id,
        normalized_company_name,
        normalized_job_title

    from {{ ref('int_job_posting_groups') }}

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

    -- Keep the latest observation with the existing tie-break order.
    select distinct on (source, job_id)
        source,
        job_id,
        search_country,
        search_role,
        extract_date

    from observations

    order by
        source, job_id,
        extract_date desc, observed_at desc, search_country, search_role

),

latest_postings as (

    select
        md5(job_postings.source || '|' || job_postings.job_id) as latest_posting_id,
        job_postings.source,
        job_postings.job_id,
        posting_groups.posting_group_id,
        job_postings.job_title,
        job_postings.company_name,
        job_postings.company_name_was_missing,
        job_postings.location,
        job_postings.country,
        latest_observation.search_country,
        latest_observation.search_role,
        posting_groups.normalized_company_name,
        posting_groups.normalized_job_title,
        job_postings.posted_date,
        case
            when job_postings.posted_date is not null
                then greatest(observation_summary.latest_extract_date - job_postings.posted_date, 0)
        end as posting_age_days,
        coalesce(
            observation_summary.latest_extract_date - job_postings.posted_date > 90,
            false
        ) as is_stale_at_latest_observation,
        job_postings.is_training_or_placement,
        job_postings.description_length,
        job_postings.description_is_source_snippet,
        job_postings.description_is_likely_truncated,
        job_postings.salary_min,
        job_postings.salary_max,
        job_postings.salary_is_available,
        job_postings.salary_range_is_complete,
        job_postings.currency,
        job_postings.salary_currency_was_inferred,
        job_postings.salary_is_predicted,
        job_postings.contract_type,
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

    left join posting_groups
        on job_postings.source = posting_groups.source
        and job_postings.job_id = posting_groups.job_id

)

select *
from latest_postings
