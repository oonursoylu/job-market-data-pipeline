{{ config(materialized='table') }}

-- Calendar for reporting tools: one row per day for every full year with observations,
-- so Power BI can mark it as a date table. is_collection_date shows which days have data;
-- days without collection are not zero-demand days.
with bounds as (

    select
        date_trunc('year', min(extract_date))::date as first_day,
        (date_trunc('year', max(extract_date)) + interval '1 year - 1 day')::date as last_day

    from {{ ref('stg_job_posting_observations') }}

),

calendar as (

    select generate_series(first_day, last_day, interval '1 day')::date as date_day
    from bounds

),

collected as (

    select
        extract_date,
        count(distinct search_country || '|' || search_role) as collected_segments

    from {{ ref('stg_job_posting_observations') }}

    group by extract_date

)

select
    calendar.date_day,
    extract(year from calendar.date_day)::int as year_number,
    extract(quarter from calendar.date_day)::int as quarter_number,
    'Q' || extract(quarter from calendar.date_day)::int as quarter_label,
    extract(month from calendar.date_day)::int as month_number,
    to_char(calendar.date_day, 'FMMonth') as month_name,
    to_char(calendar.date_day, 'Mon YYYY') as month_label,
    (extract(year from calendar.date_day) * 100 + extract(month from calendar.date_day))::int as year_month_number,
    date_trunc('week', calendar.date_day)::date as week_start_date,
    extract(isodow from calendar.date_day)::int as iso_day_of_week,
    to_char(calendar.date_day, 'FMDay') as day_name,
    extract(isodow from calendar.date_day) in (6, 7) as is_weekend,
    collected.extract_date is not null as is_collection_date,
    coalesce(collected.collected_segments, 0) as collected_segments

from calendar
left join collected
    on calendar.date_day = collected.extract_date
