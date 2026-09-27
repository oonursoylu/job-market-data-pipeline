import os

import pandas as pd
import psycopg2


# Every query reads the dbt star schema. The counting rules are described on
# fct_job_observations in dbt_job_market/models/marts/star/star_schema.yml.
# collate "C" keeps the original pandas order, which compares strings like Python.
SCOPE = """
    selected_segments as (
        select segment_id
        from analytics.dim_segments
        where is_reporting_segment
            and search_country = any(%(countries)s::text[])
            and search_role = any(%(roles)s::text[])
    ),
    scoped as (
        select observations.*
        from analytics.fct_job_observations as observations
        inner join selected_segments
            on observations.segment_id = selected_segments.segment_id
    )
"""

SKILL_WINDOW = """
    window_observations as (
        select extract_date, segment_id, posting_group_id
        from scoped
        where extract_date between %(start)s and %(end)s
    ),
    -- A date is included only when every selected segment was observed on it.
    included_dates as (
        select extract_date
        from window_observations
        group by extract_date
        having count(distinct segment_id) = (select count(*) from selected_segments)
    ),
    observed_groups as (
        select
            window_observations.extract_date,
            count(distinct window_observations.posting_group_id) as observed_groups
        from window_observations
        inner join included_dates
            on window_observations.extract_date = included_dates.extract_date
        group by window_observations.extract_date
    ),
    -- A group counts once per skill and date, across the selected roles.
    groups_with_mention as (
        select
            window_observations.extract_date,
            bridge.skill,
            count(distinct window_observations.posting_group_id) as groups_with_mention
        from window_observations
        inner join included_dates
            on window_observations.extract_date = included_dates.extract_date
        inner join analytics.bridge_posting_group_skills as bridge
            on window_observations.posting_group_id = bridge.posting_group_id
        group by window_observations.extract_date, bridge.skill
    )
"""

SNAPSHOT = """
    snapshot as (
        select job_posting_key, bool_or(is_stale_at_observation) as is_stale
        from scoped
        where extract_date = %(snapshot_date)s
        group by job_posting_key
    )
"""


def connect():
    connection = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"), connect_timeout=5,
    )
    connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
    with connection.cursor() as cursor:
        cursor.execute("SET statement_timeout = 20000")
    return connection


def read_frame(connection, query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return pd.DataFrame(cursor.fetchall(), columns=[item[0] for item in cursor.description])


def scope_params(countries, roles, **values):
    return {"countries": list(countries), "roles": list(roles), **values}


def reporting_segments(connection):
    return read_frame(connection, """
        select segment_id, search_country, country_name, search_role, role_name, segment_name
        from analytics.dim_segments
        where is_reporting_segment
        order by country_sort_order, role_sort_order
    """)


def observed_dates(connection, countries, roles):
    frame = read_frame(connection, f"""
        with {SCOPE}
        select distinct extract_date
        from scoped
        order by extract_date desc
    """, scope_params(countries, roles))
    return frame.extract_date.tolist()


def snapshot_counts(connection, countries, roles, snapshot_date):
    return read_frame(connection, f"""
        with {SCOPE}
        select
            count(distinct job_posting_key) as source_postings,
            count(distinct posting_group_id) as analytical_groups
        from scoped
        where extract_date = %(snapshot_date)s
    """, scope_params(countries, roles, snapshot_date=snapshot_date)).iloc[0]


def segment_counts(connection, countries, roles, snapshot_date):
    return read_frame(connection, f"""
        with {SCOPE}
        select
            segments.segment_name,
            count(distinct scoped.job_posting_key) as source_postings,
            count(distinct scoped.posting_group_id) as analytical_groups
        from scoped
        inner join analytics.dim_segments as segments
            on scoped.segment_id = segments.segment_id
        where scoped.extract_date = %(snapshot_date)s
        group by segments.segment_name, segments.country_sort_order, segments.role_sort_order
        order by segments.country_sort_order, segments.role_sort_order
    """, scope_params(countries, roles, snapshot_date=snapshot_date))


def archive_counts(connection, countries, roles):
    return read_frame(connection, f"""
        with {SCOPE}
        select
            count(distinct job_posting_key) as source_postings,
            count(distinct extract_date) as observed_dates
        from scoped
    """, scope_params(countries, roles)).iloc[0]


def skill_metrics(connection, countries, roles, start, end):
    # Both frames are empty when no date in the window has every selected segment.
    params = scope_params(countries, roles, start=start, end=end)
    summary = read_frame(connection, f"""
        with {SCOPE}, {SKILL_WINDOW},
        totals as (
            select count(*) as included_dates, sum(observed_groups) as observed_group_days
            from observed_groups
        )
        select
            skills.skill,
            skills.skill_label,
            skills.category,
            coalesce(sum(groups_with_mention.groups_with_mention), 0)::bigint as group_days_with_mention,
            coalesce(sum(groups_with_mention.groups_with_mention), 0)::float8
                / totals.observed_group_days::float8 * 100 as share_of_observed_group_days,
            coalesce(sum(groups_with_mention.groups_with_mention), 0)::float8
                / totals.included_dates::float8 as average_groups_per_observed_day,
            totals.included_dates,
            totals.observed_group_days::bigint as observed_group_days
        from analytics.dim_skills as skills
        cross join totals
        left join groups_with_mention
            on skills.skill = groups_with_mention.skill
        where totals.included_dates > 0
        group by
            skills.skill, skills.skill_label, skills.category,
            totals.included_dates, totals.observed_group_days
        order by group_days_with_mention desc, skills.skill_label collate "C"
    """, params)
    daily = read_frame(connection, f"""
        with {SCOPE}, {SKILL_WINDOW}
        select
            observed_groups.extract_date,
            skills.skill,
            coalesce(groups_with_mention.groups_with_mention, 0) as groups_with_mention,
            observed_groups.observed_groups
        from observed_groups
        cross join analytics.dim_skills as skills
        left join groups_with_mention
            on observed_groups.extract_date = groups_with_mention.extract_date
            and skills.skill = groups_with_mention.skill
        order by observed_groups.extract_date, skills.skill
    """, params)
    return summary, daily


def snapshot_postings(connection, countries, roles, snapshot_date):
    return read_frame(connection, f"""
        with {SCOPE}, {SNAPSHOT}
        select
            postings.source,
            postings.job_id,
            postings.job_title,
            postings.company_name,
            postings.location,
            postings.posted_date,
            postings.redirect_url
        from snapshot
        inner join analytics.dim_job_postings as postings
            on snapshot.job_posting_key = postings.job_posting_key
        order by
            postings.posted_date desc nulls last,
            postings.job_title collate "C",
            postings.company_name collate "C",
            postings.source collate "C",
            postings.job_id collate "C"
    """, scope_params(countries, roles, snapshot_date=snapshot_date))


def quality_counts(connection, countries, roles, snapshot_date):
    return read_frame(connection, f"""
        with {SCOPE}, {SNAPSHOT}
        select
            count(*) as source_postings,
            count(*) filter (where postings.company_name_was_missing) as missing_companies,
            count(*) filter (where postings.description_is_likely_truncated) as likely_truncated,
            count(*) filter (where postings.salary_is_available) as salaries_available,
            count(*) filter (where snapshot.is_stale) as stale_postings,
            count(*) filter (where postings.is_training_or_placement) as training_postings,
            count(*) filter (
                where postings.salary_is_available and postings.salary_currency_was_inferred
            ) as inferred_currency
        from snapshot
        inner join analytics.dim_job_postings as postings
            on snapshot.job_posting_key = postings.job_posting_key
    """, scope_params(countries, roles, snapshot_date=snapshot_date)).iloc[0]


def repeated_groups(connection, countries, roles, snapshot_date, limit=20):
    return read_frame(connection, f"""
        with {SCOPE}, {SNAPSHOT}
        select
            postings.posting_group_id,
            min(postings.company_name) as company,
            min(postings.job_title) as title,
            count(*) as source_postings,
            count(distinct postings.location) as locations
        from snapshot
        inner join analytics.dim_job_postings as postings
            on snapshot.job_posting_key = postings.job_posting_key
        group by postings.posting_group_id
        having count(*) > 1
        order by source_postings desc, company, title, postings.posting_group_id
        limit %(limit)s
    """, scope_params(countries, roles, snapshot_date=snapshot_date, limit=limit))


def coverage(connection, countries, roles):
    return read_frame(connection, f"""
        with {SCOPE}
        select
            scoped.extract_date,
            scoped.search_country,
            scoped.search_role,
            segments.segment_name,
            count(distinct scoped.job_posting_key) as source_postings
        from scoped
        inner join analytics.dim_segments as segments
            on scoped.segment_id = segments.segment_id
        group by scoped.extract_date, scoped.search_country, scoped.search_role, segments.segment_name
        order by scoped.extract_date desc, scoped.search_country collate "C", scoped.search_role collate "C"
    """, scope_params(countries, roles))
