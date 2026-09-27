{{ config(materialized='table') }}

-- One row per source posting, with its analytical group.
with job_postings as (

    select
        source,
        job_id,
        job_title,
        company_name,
        company_name_was_missing,
        location,
        posted_date,
        is_training_or_placement,
        description_is_likely_truncated,
        salary_is_available,
        salary_currency_was_inferred,
        currency,
        redirect_url,
        extract_date

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
    md5(job_postings.source || '|' || job_postings.job_id) as job_posting_key,
    job_postings.source,
    job_postings.job_id,
    posting_groups.posting_group_id,
    job_postings.job_title,
    job_postings.company_name,
    job_postings.company_name_was_missing,
    job_postings.location,
    job_postings.posted_date,
    job_postings.is_training_or_placement,
    job_postings.description_is_likely_truncated,
    job_postings.salary_is_available,
    job_postings.salary_currency_was_inferred,
    job_postings.currency,
    job_postings.redirect_url,
    job_postings.extract_date as first_catalog_date

from job_postings
inner join posting_groups
    on job_postings.source = posting_groups.source
    and job_postings.job_id = posting_groups.job_id
