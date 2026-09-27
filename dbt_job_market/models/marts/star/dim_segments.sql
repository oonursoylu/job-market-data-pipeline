{{ config(materialized='table') }}

-- Display names and sort order live here, so the dashboard and BI tools share them.
-- Data Analyst is listed but kept out of reporting until enough dates are loaded.
with countries as (

    select *
    from (
        values
            ('de', 'Germany', 1),
            ('gb', 'United Kingdom', 2)
    ) as country_values (search_country, country_name, country_sort_order)

),

roles as (

    select *
    from (
        values
            ('data_engineer', 'Data Engineer', 1, true),
            ('analytics_engineer', 'Analytics Engineer', 2, true),
            ('ai_engineer', 'AI Engineer', 3, true),
            ('data_analyst', 'Data Analyst', 4, false)
    ) as role_values (search_role, role_name, role_sort_order, is_reporting_segment)

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
    roles.is_reporting_segment

from countries
cross join roles
