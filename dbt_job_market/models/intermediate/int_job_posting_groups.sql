{{ config(materialized='table') }}

with job_postings as (

    select
        source,
        job_id,
        search_country,
        search_role,
        job_title,
        company_name,
        company_name_was_missing,
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
        company_name_was_missing,
        location,
        posted_date,
        extract_date,

        {{ normalize_text("coalesce(company_name, '')") }} as normalized_company_name,
        case
            when company_name_was_missing then 'missing-company:' || job_id
            else {{ normalize_text('company_name') }}
        end as company_group_key,
        {{ normalize_text("coalesce(job_title, '')") }} as normalized_job_title,

        md5({{ normalize_text("coalesce(description, '')") }}) as description_hash

    from job_postings

),

grouped as (

    select
        md5(
            source || '|' ||
            search_country || '|' ||
            company_group_key || '|' ||
            normalized_job_title || '|' ||
            description_hash
        ) as posting_group_id,
        source,
        job_id,
        search_country,
        search_role,
        job_title,
        company_name,
        company_name_was_missing,
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
