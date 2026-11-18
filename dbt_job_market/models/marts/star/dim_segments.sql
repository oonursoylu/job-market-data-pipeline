{{ config(materialized='table') }}

-- Display names, sort order and collection start dates come from the
-- search_countries and search_roles seeds, which the Python extractor also reads.
-- is_reporting_segment can hide a role that is collected but not ready to report.
with countries as (

    select
        search_country,
        country_name,
        country_sort_order,
        collection_start_date

    from {{ ref('search_countries') }}

),

roles as (

    select
        search_role,
        role_name,
        role_sort_order,
        is_reporting_segment,
        collection_start_date

    from {{ ref('search_roles') }}

)

select
    countries.search_country || '|' || roles.search_role as segment_id,
    countries.search_country,
    countries.country_name,
    countries.country_sort_order,
    roles.search_role,
    roles.role_name,
    roles.role_sort_order,
    countries.country_name || ' / ' || roles.role_name as segment_name,
    row_number() over (
        order by countries.country_sort_order, roles.role_sort_order
    ) as segment_sort_order,
    roles.is_reporting_segment,
    greatest(countries.collection_start_date, roles.collection_start_date) as collection_start_date

from countries
cross join roles
