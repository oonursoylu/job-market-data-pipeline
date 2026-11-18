with source as (

    select *
    from {{ source('raw', 'job_postings') }}

),

countries as (

    select
        search_country,
        salary_currency

    from {{ ref('search_countries') }}

),

cleaned as (

    select
        source,
        job_id,
        nullif(trim(job_title), '') as job_title,
        nullif(trim(company_name), '') as source_company_name,
        nullif(trim(location), '') as location,
        nullif(trim(country), '') as country,
        nullif(trim(description), '') as description,
        char_length(description) as source_description_length,
        salary_min as source_salary_min,
        salary_max as source_salary_max,
        nullif(upper(trim(currency)), '') as source_currency,
        nullif(trim(contract_type), '') as contract_type,
        nullif(trim(category), '') as category,
        nullif(trim(redirect_url), '') as redirect_url,
        created_at,
        created_at::date as posted_date,
        source.search_role,
        source.search_country,
        countries.salary_currency as country_salary_currency,
        raw_json,
        loaded_at,
        extract_date

    from source
    left join countries
        on source.search_country = countries.search_country

),

prepared as (

    select
        source,
        job_id,
        job_title,
        coalesce(source_company_name, 'Unknown') as company_name,
        source_company_name is null as company_name_was_missing,
        location,
        country,
        -- English and German training-style titles: Werkstudent, Praktikum, Ausbildung,
        -- duales Studium and thesis adverts are flagged, not removed.
        coalesce(
            lower(job_title) ~ (
                '(^|[^a-zäöüß])('
                || 'trainees?|apprentices?|apprenticeships?|interns?|internships?|working students?'
                || '|werkstudent(in|innen|en)?|werkstudierende[rn]?'
                || '|(pflicht)?praktikum|praktikant(in|innen|en)?'
                || '|ausbildung|azubis?|auszubildende[rn]?'
                || '|duales studium|duale[rnms]? student(in|innen|en)?'
                || '|abschlussarbeit(en)?|masterarbeit|bachelorarbeit|thesis'
                || ')([^a-zäöüß]|$)'
            )
            or lower(job_title) like '%placement programme%'
            or lower(job_title) like '%career switch%'
            or lower(job_title) like '%no experience needed%',
            false
        ) as is_training_or_placement,
        description,
        source_description_length as description_length,
        source = 'adzuna' as description_is_source_snippet,
        source = 'adzuna' and coalesce(source_description_length, 0) >= 500
            as description_is_likely_truncated,
        source_salary_min,
        source_salary_max,
        case when source_salary_min > 0 then source_salary_min end as salary_min,
        case when source_salary_max > 0 then source_salary_max end as salary_max,
        coalesce(source_salary_min > 0, false)
            or coalesce(source_salary_max > 0, false) as salary_is_available,
        coalesce(source_salary_min > 0, false)
            and coalesce(source_salary_max > 0, false) as salary_range_is_complete,
        case
            when coalesce(source_salary_min > 0, false)
                or coalesce(source_salary_max > 0, false)
                then coalesce(source_currency, country_salary_currency)
        end as currency,
        source_currency,
        (coalesce(source_salary_min > 0, false)
            or coalesce(source_salary_max > 0, false))
            and source_currency is null
            and country_salary_currency is not null
            as salary_currency_was_inferred,
        case raw_json ->> 'salary_is_predicted'
            when '1' then true
            when '0' then false
        end as salary_is_predicted,
        contract_type,
        category,
        redirect_url,
        created_at,
        posted_date,
        search_role,
        search_country,
        raw_json,
        loaded_at,
        extract_date

    from cleaned

)

select *
from prepared
