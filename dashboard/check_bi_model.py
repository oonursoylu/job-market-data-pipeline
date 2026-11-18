import itertools
import sys

from dotenv import load_dotenv

import queries


# Checks that the columns added for BI tools give the dashboard's skill numbers.
# The SQL below follows the DAX measures in docs/power_bi_model.md step by step:
#   included dates  = dates on which fct_segment_coverage has every selected segment
#   group-days      = distinct group_day_key on included dates
#   with a skill    = the same distinct count, filtered through the skill bridge
# Run from the repository root after dbt build:
#   python dashboard\check_bi_model.py
BI_SQL = """
    with selected_segments as (
        select segment_id
        from analytics.dim_segments
        where is_reporting_segment
            and search_country = any(%(countries)s::text[])
            and search_role = any(%(roles)s::text[])
    ),
    included_dates as (
        select coverage.extract_date
        from analytics.fct_segment_coverage as coverage
        inner join selected_segments on coverage.segment_id = selected_segments.segment_id
        where coverage.extract_date between %(start)s and %(end)s
        group by coverage.extract_date
        having count(*) = (select count(*) from selected_segments)
    ),
    scoped as (
        select observations.group_day_key, observations.posting_group_id
        from analytics.fct_job_observations as observations
        inner join selected_segments on observations.segment_id = selected_segments.segment_id
        inner join included_dates on observations.extract_date = included_dates.extract_date
    ),
    totals as (
        select (select count(*) from included_dates) as included_dates,
               count(distinct group_day_key) as observed_group_days
        from scoped
    )
    select skills.skill,
           count(distinct scoped.group_day_key) as group_days_with_mention,
           totals.included_dates,
           totals.observed_group_days
    from analytics.dim_skills as skills
    cross join totals
    left join analytics.bridge_posting_group_skills as bridge on bridge.skill = skills.skill
    left join scoped on scoped.posting_group_id = bridge.posting_group_id
    where totals.included_dates > 0
    group by skills.skill, totals.included_dates, totals.observed_group_days
"""


def main() -> int:
    load_dotenv()
    connection = queries.connect()
    try:
        segments = queries.reporting_segments(connection)
        countries = list(dict.fromkeys(segments.search_country))
        roles = list(dict.fromkeys(segments.search_role))
        dates = sorted(queries.observed_dates(connection, countries, roles))
        windows = [(dates[0], dates[-1]), (dates[-1], dates[-1])]
        checked = failed = 0
        for country_count in range(1, len(countries) + 1):
            for role_count in range(1, len(roles) + 1):
                for scope_countries in itertools.combinations(countries, country_count):
                    for scope_roles in itertools.combinations(roles, role_count):
                        for start, end in windows:
                            expected, _ = queries.skill_metrics(connection, scope_countries, scope_roles, start, end)
                            actual = queries.read_frame(connection, BI_SQL, queries.scope_params(
                                scope_countries, scope_roles, start=start, end=end))
                            columns = ["skill", "group_days_with_mention", "included_dates", "observed_group_days"]
                            expected = expected[columns].sort_values("skill").reset_index(drop=True)
                            actual = actual[columns].sort_values("skill").reset_index(drop=True)
                            checked += 1
                            if not expected.astype(str).equals(actual.astype(str)):
                                failed += 1
                                print(f"Difference: {scope_countries} {scope_roles} {start}..{end}")
        print(f"BI model check: {checked} scopes compared, {failed} with differences.")
        return 1 if failed else 0
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
