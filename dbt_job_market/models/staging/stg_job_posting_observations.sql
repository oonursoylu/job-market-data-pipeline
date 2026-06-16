with raw_observations as (

    select *
    from {{ source('raw', 'job_posting_observations') }}

),

renamed as (

    select
        md5(concat_ws('|', source, job_id, search_country, search_role, extract_date::text)) as observation_id,
        source,
        job_id,
        search_role,
        search_country,
        extract_date,
        observed_at

    from raw_observations

)

select *
from renamed