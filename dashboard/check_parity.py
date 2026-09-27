import itertools
import sys
from collections import Counter

import pandas as pd
from dotenv import load_dotenv

import queries


# Compares the SQL in queries.py with the pandas logic the dashboard used before
# it moved to the star schema. The reference functions are copied from that
# version of app.py. Skill labels come from dim_skills, so the corrected labels
# do not change the tie-break order. Run from the repository root after dbt build:
#   python dashboard\check_parity.py
COUNTRIES = {"de": "Germany", "gb": "United Kingdom"}
ROLES = {
    "data_engineer": "Data Engineer",
    "analytics_engineer": "Analytics Engineer",
    "ai_engineer": "AI Engineer",
}
POSTING_COLUMNS = ["source", "job_id", "job_title", "company_name", "location", "posted_date", "redirect_url"]
QUALITY_COLUMNS = [
    "source_postings", "missing_companies", "likely_truncated", "salaries_available",
    "stale_postings", "training_postings", "inferred_currency",
]
OBSERVATIONS_SQL = """
    select o.source, o.job_id, o.search_country, o.search_role, o.extract_date,
           g.posting_group_id, p.job_title, p.company_name, p.location,
           p.company_name_was_missing, p.description_is_likely_truncated,
           p.is_training_or_placement,
           p.salary_is_available, p.salary_currency_was_inferred, p.currency,
           p.posted_date,
           case when p.posted_date is not null
                then greatest(o.extract_date - p.posted_date, 0) end as posting_age_days,
           coalesce(o.extract_date - p.posted_date > 90, false) as is_stale,
           p.redirect_url
    from analytics.stg_job_posting_observations o
    join analytics.stg_job_postings p using (source, job_id)
    join analytics.int_job_posting_groups g using (source, job_id)
    where o.search_country in ('de', 'gb')
      and o.search_role in ('data_engineer', 'analytics_engineer', 'ai_engineer')
"""


def load_reference(connection):
    observations = queries.read_frame(connection, OBSERVATIONS_SQL)
    skills = queries.read_frame(connection, """
        select source, job_id, skill, category
        from analytics.int_job_posting_skills
    """)
    dictionary = queries.read_frame(connection, "select skill, category from analytics.skill_dictionary")
    observations["extract_date"] = pd.to_datetime(observations.extract_date).dt.date
    return observations, skills, dictionary


def scope_rows(frame, countries, roles):
    return frame[frame.search_country.isin(countries) & frame.search_role.isin(roles)].copy()


def reference_skill_metrics(observations, skills, dictionary, countries, roles, start, end, skill_label):
    selected = scope_rows(observations, countries, roles)
    selected = selected[selected.extract_date.between(start, end)]
    # Compare only dates with observations in every selected segment.
    coverage = selected.drop_duplicates(["extract_date", "search_country", "search_role"])
    counts = coverage.groupby("extract_date").size()
    dates = counts[counts == len(countries) * len(roles)].index
    selected = selected[selected.extract_date.isin(dates)]
    denominator = selected.groupby("extract_date").posting_group_id.nunique().sort_index()
    matches = selected.merge(skills, on=["source", "job_id"], how="inner")
    matches = matches.drop_duplicates(["extract_date", "posting_group_id", "skill"])
    all_skills = dictionary.skill.tolist()
    if denominator.empty:
        return pd.DataFrame(), pd.DataFrame(), denominator
    daily = matches.groupby(["extract_date", "skill"]).size().unstack(fill_value=0)
    daily = daily.reindex(index=denominator.index, columns=all_skills, fill_value=0).fillna(0)
    # No match on an observed date is zero. Uncollected dates are not added.
    summary = dictionary.copy().set_index("skill")
    summary["Group-days with mention"] = daily.sum()
    summary["Share of observed group-days (%)"] = daily.sum() / denominator.sum() * 100
    summary["Average groups per observed day"] = daily.mean()
    summary = summary.reset_index()
    summary["Skill"] = summary.skill.map(skill_label)
    return summary.sort_values(["Group-days with mention", "Skill"], ascending=[False, True]), daily, denominator


def unique_postings(snapshot):
    return snapshot.sort_values(["source", "job_id", "search_role"]).drop_duplicates(["source", "job_id"])


def reference_segments(snapshot):
    by_role = snapshot.groupby(["search_country", "search_role"]).agg(
        source_postings=("job_id", "nunique"), analytical_groups=("posting_group_id", "nunique")
    ).reset_index()
    country_order = {country: index for index, country in enumerate(COUNTRIES)}
    role_order = {role: index for index, role in enumerate(ROLES)}
    by_role["country_order"] = by_role.search_country.map(country_order)
    by_role["role_order"] = by_role.search_role.map(role_order)
    by_role = by_role.sort_values(["country_order", "role_order"], kind="stable")
    by_role["Segment"] = by_role.search_country.map(COUNTRIES) + " / " + by_role.search_role.map(ROLES)
    return by_role


def reference_postings(snapshot):
    return unique_postings(snapshot).sort_values(
        ["posted_date", "job_title", "company_name"],
        ascending=[False, True, True],
        na_position="last",
        kind="stable",
    )


def reference_quality(snapshot):
    quality_posts = unique_postings(snapshot)
    return {
        "source_postings": len(quality_posts),
        "missing_companies": int(quality_posts.company_name_was_missing.fillna(False).sum()),
        "likely_truncated": int(quality_posts.description_is_likely_truncated.fillna(False).sum()),
        "salaries_available": int(quality_posts.salary_is_available.fillna(False).sum()),
        "stale_postings": int(quality_posts.is_stale.fillna(False).sum()),
        "training_postings": int(quality_posts.is_training_or_placement.fillna(False).sum()),
        "inferred_currency": int(
            quality_posts.loc[quality_posts.salary_is_available, "salary_currency_was_inferred"]
            .fillna(False)
            .sum()
        ),
    }


def reference_repeated(snapshot):
    repeated = snapshot.drop_duplicates(["source", "job_id"]).groupby("posting_group_id").agg(
        Company=("company_name", "first"), Title=("job_title", "first"),
        Source_postings=("job_id", "size"), Locations=("location", "nunique")
    ).reset_index()
    return repeated[repeated.Source_postings > 1].sort_values("Source_postings", ascending=False)


def reference_coverage(scoped):
    coverage = scoped.groupby(["extract_date", "search_country", "search_role"]).job_id.nunique().reset_index(name="Source postings")
    return coverage.sort_values(["extract_date", "search_country", "search_role"], ascending=[False, True, True])


def plain(value):
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if not isinstance(value, str) and pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def rows(frame, columns):
    return plain(list(frame[columns].itertuples(index=False, name=None)))


class Checks:
    def __init__(self):
        self.names = []
        self.passed = Counter()
        self.failed = Counter()
        self.examples = []
        self.scopes = 0
        self.snapshots = 0

    def expect(self, name, context, old, new):
        if name not in self.names:
            self.names.append(name)
        old, new = plain(old), plain(new)
        if old == new:
            self.passed[name] += 1
            return
        self.failed[name] += 1
        if len(self.examples) < 10:
            self.examples.append(f"{name} [{context}]\n  old: {str(old)[:300]}\n  new: {str(new)[:300]}")


def compare_repeated(checks, context, snapshot, new):
    old = reference_repeated(snapshot)
    checks.expect("repeated groups", context,
        sorted(rows(old, ["posting_group_id", "Source_postings", "Locations"])),
        sorted(rows(new, ["posting_group_id", "source_postings", "locations"])))
    # The old table left ties in no fixed order, so only its top 20 counts are fixed.
    checks.expect("repeated groups top 20 counts", context,
        old.Source_postings.head(20).tolist(), new.source_postings.head(20).tolist())
    companies, titles = {}, {}
    for row in unique_postings(snapshot).itertuples():
        companies.setdefault(row.posting_group_id, set()).add(row.company_name)
        titles.setdefault(row.posting_group_id, set()).add(row.job_title)
    checks.expect("repeated group names come from members", context, True, all(
        row.company in companies[row.posting_group_id] and row.title in titles[row.posting_group_id]
        for row in new.itertuples()
    ))


def compare_skills(checks, context, old, new):
    old_summary, old_daily, old_observed = old
    new_summary, new_daily = new
    checks.expect("skill window is empty", context, old_summary.empty, new_summary.empty)
    if old_summary.empty or new_summary.empty:
        return
    checks.expect("included dates and group-days", context,
        [len(old_observed), old_observed.sum()],
        [new_summary.included_dates.iloc[0], new_summary.observed_group_days.iloc[0]])
    checks.expect("observed groups per date", context,
        list(old_observed.items()),
        rows(new_daily.drop_duplicates("extract_date"), ["extract_date", "observed_groups"]))
    checks.expect("skill ranking and values", context,
        rows(old_summary, ["skill", "Skill", "category", "Group-days with mention",
                           "Share of observed group-days (%)", "Average groups per observed day"]),
        rows(new_summary, ["skill", "skill_label", "category", "group_days_with_mention",
                           "share_of_observed_group_days", "average_groups_per_observed_day"]))
    old_cells = sorted(
        (day, skill, count)
        for day, values in zip(old_daily.index, old_daily.to_numpy().tolist())
        for skill, count in zip(old_daily.columns, values)
    )
    checks.expect("daily skill counts", context, old_cells,
        sorted(rows(new_daily, ["extract_date", "skill", "groups_with_mention"])))


def scopes():
    for country_count in range(1, len(COUNTRIES) + 1):
        for countries in itertools.combinations(COUNTRIES, country_count):
            for role_count in range(1, len(ROLES) + 1):
                for roles in itertools.combinations(ROLES, role_count):
                    yield list(countries), list(roles)


def run_checks(connection, max_dates=None):
    checks = Checks()
    observations, skills, dictionary = load_reference(connection)
    labels = dict(queries.read_frame(connection, "select skill, skill_label from analytics.dim_skills")
                  .itertuples(index=False, name=None))
    for countries, roles in scopes():
        checks.scopes += 1
        scope_name = f"{'+'.join(countries)} | {'+'.join(roles)}"
        scoped = scope_rows(observations, countries, roles)
        available_dates = sorted(scoped.extract_date.unique(), reverse=True)
        checks.expect("observed dates", scope_name, available_dates,
            queries.observed_dates(connection, countries, roles))
        archive = queries.archive_counts(connection, countries, roles)
        checks.expect("archive counts", scope_name,
            [len(scoped.drop_duplicates(["source", "job_id"])), scoped.extract_date.nunique()],
            [archive.source_postings, archive.observed_dates])
        checks.expect("coverage table", scope_name,
            rows(reference_coverage(scoped), ["extract_date", "search_country", "search_role", "Source postings"]),
            rows(queries.coverage(connection, countries, roles),
                 ["extract_date", "search_country", "search_role", "source_postings"]))
        for snapshot_date in available_dates[:max_dates]:
            checks.snapshots += 1
            context = f"{scope_name} | {snapshot_date}"
            snapshot = scoped[scoped.extract_date == snapshot_date]
            counts = queries.snapshot_counts(connection, countries, roles, snapshot_date)
            checks.expect("snapshot counts", context,
                [len(snapshot.drop_duplicates(["source", "job_id"])), snapshot.posting_group_id.nunique()],
                [counts.source_postings, counts.analytical_groups])
            checks.expect("segment table", context,
                rows(reference_segments(snapshot), ["Segment", "source_postings", "analytical_groups"]),
                rows(queries.segment_counts(connection, countries, roles, snapshot_date),
                     ["segment_name", "source_postings", "analytical_groups"]))
            checks.expect("posting list", context,
                rows(reference_postings(snapshot), POSTING_COLUMNS),
                rows(queries.snapshot_postings(connection, countries, roles, snapshot_date), POSTING_COLUMNS))
            quality = queries.quality_counts(connection, countries, roles, snapshot_date)
            checks.expect("quality counts", context, reference_quality(snapshot),
                {name: quality[name] for name in QUALITY_COLUMNS})
            compare_repeated(checks, context, snapshot,
                queries.repeated_groups(connection, countries, roles, snapshot_date, limit=None))
            windows = [
                ("snapshot", snapshot_date),
                ("last 30 days", (pd.Timestamp(snapshot_date) - pd.Timedelta(days=29)).date()),
                ("all dates", min(available_dates)),
            ]
            for window, start in windows:
                compare_skills(checks, f"{context} | {window}",
                    reference_skill_metrics(observations, skills, dictionary, countries, roles,
                                            start, snapshot_date, labels.get),
                    queries.skill_metrics(connection, countries, roles, start, snapshot_date))
    return checks


def main():
    load_dotenv()
    connection = queries.connect()
    try:
        checks = run_checks(connection)
    finally:
        connection.rollback()
        connection.close()
    print(f"{checks.scopes} scopes, {checks.snapshots} snapshot dates\n")
    for name in checks.names:
        print(f"{name}: {checks.passed[name]} passed, {checks.failed[name]} failed")
    failed = sum(checks.failed.values())
    print(f"\nTotal: {sum(checks.passed.values())} passed, {failed} failed")
    for example in checks.examples:
        print(f"\n{example}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
