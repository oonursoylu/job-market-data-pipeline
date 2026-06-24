{{ config(materialized='table') }}

with job_postings as (

    select
        source,
        job_id,
        search_country,
        search_role,
        job_title,
        company_name,
        location,
        description,
        posted_date,
        extract_date

    from {{ ref('stg_job_postings') }}

),

normalized as (

    select
        source,
        job_id,
        search_country,
        search_role,
        job_title,
        company_name,
        location,
        posted_date,
        extract_date,

        trim(regexp_replace(lower(coalesce(company_name, '')), '[^a-z0-9]+', ' ', 'g')) as normalized_company_name,
        trim(regexp_replace(lower(coalesce(job_title, '')), '[^a-z0-9]+', ' ', 'g')) as normalized_job_title,

        md5(
            trim(regexp_replace(lower(coalesce(description, '')), '[^a-z0-9]+', ' ', 'g'))
        ) as description_hash

    from job_postings

),

grouped as (

    select
        md5(
            source || '|' ||
            search_country || '|' ||
            normalized_company_name || '|' ||
            normalized_job_title || '|' ||
            description_hash
        ) as posting_group_id,
        source,
        job_id,
        search_country,
        search_role,
        job_title,
        company_name,
        location,
        normalized_company_name,
        normalized_job_title,
        description_hash,
        posted_date,
        extract_date

    from normalized

)

select *
from grouped