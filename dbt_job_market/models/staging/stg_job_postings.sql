with source as (

    select *
    from {{ source('raw', 'job_postings') }}

),

renamed as (

    select
        source,
        job_id,
        nullif(trim(job_title), '') as job_title,
        nullif(trim(company_name), '') as company_name,
        nullif(trim(location), '') as location,
        nullif(trim(country), '') as country,
        nullif(trim(description), '') as description,
        salary_min,
        salary_max,
        nullif(trim(currency), '') as currency,
        nullif(trim(contract_type), '') as contract_type,
        nullif(trim(category), '') as category,
        nullif(trim(redirect_url), '') as redirect_url,
        created_at,
        created_at::date as posted_date,
        search_role,
        search_country,
        raw_json,
        loaded_at,
        extract_date

    from source

)

select *
from renamed