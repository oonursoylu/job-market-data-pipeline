import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

import queries


load_dotenv()
PLOTLY_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "responsive": True,
}
SKILL_COLUMNS = {
    "skill_label": "Skill",
    "group_days_with_mention": "Group-days with mention",
    "share_of_observed_group_days": "Share of observed group-days (%)",
    "average_groups_per_observed_day": "Average groups per observed day",
}


def with_connection(read):
    connection = queries.connect()
    try:
        return read(connection)
    finally:
        connection.rollback()
        connection.close()


# Each loader reads in one transaction. Refresh data clears all of them.
@st.cache_data(ttl=300)
def load_segments():
    return with_connection(queries.reporting_segments)


@st.cache_data(ttl=300)
def load_scope(countries, roles):
    return with_connection(lambda connection: (
        queries.observed_dates(connection, countries, roles),
        queries.archive_counts(connection, countries, roles),
        queries.coverage(connection, countries, roles),
    ))


@st.cache_data(ttl=300)
def load_snapshot(countries, roles, snapshot_date):
    return with_connection(lambda connection: (
        queries.snapshot_counts(connection, countries, roles, snapshot_date),
        queries.segment_counts(connection, countries, roles, snapshot_date),
        queries.snapshot_postings(connection, countries, roles, snapshot_date),
        queries.quality_counts(connection, countries, roles, snapshot_date),
        queries.repeated_groups(connection, countries, roles, snapshot_date),
    ))


@st.cache_data(ttl=300)
def load_skills(countries, roles, start, end):
    summary, daily = with_connection(
        lambda connection: queries.skill_metrics(connection, countries, roles, start, end)
    )
    return summary.rename(columns=SKILL_COLUMNS), daily


def load(loader, *args):
    try:
        return loader(*args)
    except Exception:
        st.error("Could not load data. Check that PostgreSQL is running and the dbt models are available.")
        st.stop()


st.set_page_config(page_title="Job Market Explorer", page_icon="📊", layout="wide")
st.title("Job Market Explorer")
st.caption("Explore collected job adverts, skill mentions and repeated posting groups.")
segments = load(load_segments)
country_names = dict(segments[["search_country", "country_name"]].drop_duplicates().itertuples(index=False, name=None))
role_names = dict(segments[["search_role", "role_name"]].drop_duplicates().itertuples(index=False, name=None))
with st.sidebar:
    st.header("Scope")
    countries = st.multiselect("Countries", list(country_names), default=list(country_names), format_func=country_names.get)
    roles = st.multiselect("Search roles", list(role_names), default=list(role_names), format_func=role_names.get)
    if st.button("Refresh data"):
        st.cache_data.clear()
    st.caption("Data Analyst archives are being collected separately; reporting integration is pending.")
if not countries or not roles:
    st.info("Select at least one country and search role.")
    st.stop()
countries, roles = tuple(countries), tuple(roles)
available_dates, archive, coverage = load(load_scope, countries, roles)
if not available_dates:
    collected_dates = load(load_scope, tuple(country_names), tuple(role_names))[0]
    st.info("No observations match this scope." if collected_dates else "No observations are available yet.")
    st.stop()
snapshot_date = st.sidebar.selectbox("Snapshot date", available_dates)
counts, by_role, posts, quality, repeated = load(load_snapshot, countries, roles, snapshot_date)
st.caption(f"Snapshot: {snapshot_date} | {len(countries)} countries · {len(roles)} search roles | Skills has its own date window.")
with st.expander("How to read this dashboard"):
    st.write("One API source, with up to 150 results per country and search role in each collection. Counts describe this sample, not total market demand. Search roles can overlap.")
    st.write("Analytical groups match normalised company, title and description within each country and source. They are not verified vacancies. Reposts and similar separate jobs may share a group.")
    st.write("Skills are matched in job titles and short source-description snippets. Adzuna does not guarantee full advert text, so a missing mention is not evidence that a skill is unnecessary. Historical text is rescored when the dictionary changes.")

overview_tab, skills_tab, explore_tab, quality_tab = st.tabs(["Overview", "Skills", "Explore Postings", "Data Quality"])
with overview_tab:
    st.subheader("Selected snapshot")
    source_count = int(counts.source_postings)
    groups = int(counts.analytical_groups)
    reduction = source_count - groups
    a, b, c = st.columns(3)
    a.metric("Source postings", f"{source_count:,}")
    b.metric("Analytical groups", f"{groups:,}")
    c.metric("Fewer entries after grouping", f"{reduction:,}", help="Source count minus group count. Not a confirmed duplicate count.")
    st.caption(f"{source_count:,} source postings become {groups:,} groups. Counts fall by {reduction / source_count:.1%}; this does not prove that the difference consists of duplicate vacancies.")
    by_role["Reduction (%)"] = (1 - by_role.analytical_groups / by_role.source_postings) * 100
    chart = by_role.rename(columns={
        "segment_name": "Segment", "source_postings": "Source postings", "analytical_groups": "Analytical groups"})
    melted = chart.melt(id_vars="Segment", value_vars=["Source postings", "Analytical groups"], var_name="Measure", value_name="Count")
    segment_order = chart.Segment.tolist()
    role_figure = px.bar(
        melted,
        x="Segment",
        y="Count",
        color="Measure",
        barmode="group",
        category_orders={
            "Segment": segment_order,
            "Measure": ["Source postings", "Analytical groups"],
        },
        color_discrete_map={"Source postings": "#94a3b8", "Analytical groups": "#2563eb"},
    )
    role_figure.update_layout(legend_title_text=None, margin=dict(l=10, r=10, t=20, b=10))
    role_figure.update_yaxes(rangemode="tozero")
    st.plotly_chart(role_figure, width="stretch", config=PLOTLY_CONFIG)
    st.caption("Segment counts may overlap. The cards count source IDs and groups once across the selected snapshot.")
    with st.expander("View segment details"):
        st.dataframe(chart[["Segment", "Source postings", "Analytical groups", "Reduction (%)"]].round(1), hide_index=True, width="stretch")
    with st.expander("Accumulated archive for this scope"):
        st.write(f"{int(archive.source_postings):,} distinct source postings across {int(archive.observed_dates)} observed dates. These are not all currently open jobs.")
    st.subheader("Most mentioned skills in the selected snapshot")
    snapshot_summary, _ = load(load_skills, countries, roles, snapshot_date, snapshot_date)
    if snapshot_summary.empty:
        st.info("Skill comparison is unavailable: some selected country/role segments have no observations on this date.")
    else:
        st.caption("Share of analytical groups with a skill mention in the title or source snippet on this date. Each group counts once across selected roles. A group can mention several skills.")
        snapshot_top = snapshot_summary[snapshot_summary["Group-days with mention"] > 0].head(10)
        if snapshot_top.empty:
            st.info("No tracked skill mentions found in this snapshot.")
        else:
            snapshot_top = snapshot_top.rename(columns={"Share of observed group-days (%)": "Share of groups (%)"})
            snapshot_skill_figure = px.bar(
                snapshot_top.sort_values("Share of groups (%)"),
                x="Share of groups (%)",
                y="Skill",
                orientation="h",
                text="Share of groups (%)",
                color_discrete_sequence=["#2563eb"],
            )
            snapshot_skill_figure.update_traces(
                texttemplate="%{text:.1f}%",
                textposition="outside",
                cliponaxis=False,
                hovertemplate="<b>%{y}</b><br>Share of groups: %{x:.1f}%<extra></extra>",
            )
            snapshot_skill_figure.update_layout(margin=dict(l=10, r=45, t=20, b=10))
            snapshot_skill_figure.update_xaxes(rangemode="tozero", ticksuffix="%")
            st.plotly_chart(
                snapshot_skill_figure,
                width="stretch",
                config=PLOTLY_CONFIG,
                key="snapshot_top_skills",
            )
        st.caption("Open the Skills tab for a custom watchlist, the complete ranking and observed trends.")

with skills_tab:
    st.subheader("Which skills appear in the sample?")
    window = st.radio("Skill window", ["Last 30 calendar days", "All observed dates"], horizontal=True)
    end = snapshot_date
    start = (pd.Timestamp(end) - pd.Timedelta(days=29)).date() if window.startswith("Last") else min(available_dates)
    summary, daily = load(load_skills, countries, roles, start, end)
    st.caption(f"Window: {start} to {end}. Only dates with observations in every selected country/role segment are included. This does not prove that every API page completed.")
    if summary.empty:
        st.info("No dates have observations in every selected segment. Try a wider window or fewer segments.")
    else:
        st.caption(f"{int(summary.included_dates.iloc[0])} included dates · {int(summary.observed_group_days.iloc[0]):,} observed group-days. A group counts once per date across selected roles. The same group can count on different dates.")
        st.write("**Top skills in the collected data**")
        top = summary[summary["Group-days with mention"] > 0].head(15)
        if top.empty:
            st.info("No tracked skill mentions were found in this scope.")
        else:
            top_skill_figure = px.bar(
                top.sort_values("Share of observed group-days (%)"),
                x="Share of observed group-days (%)",
                y="Skill",
                orientation="h",
                text="Share of observed group-days (%)",
                color_discrete_sequence=["#2563eb"],
            )
            top_skill_figure.update_traces(
                texttemplate="%{text:.1f}%",
                textposition="outside",
                cliponaxis=False,
                hovertemplate="<b>%{y}</b><br>Share of group-days: %{x:.1f}%<extra></extra>",
            )
            top_skill_figure.update_layout(margin=dict(l=10, r=45, t=20, b=10))
            top_skill_figure.update_xaxes(rangemode="tozero", ticksuffix="%")
            st.plotly_chart(top_skill_figure, width="stretch", config=PLOTLY_CONFIG)
        columns = ["Skill", "Group-days with mention", "Share of observed group-days (%)", "Average groups per observed day"]
        labels = dict(zip(summary.skill, summary.Skill))
        with st.expander("Build a personal skill watchlist"):
            watched = st.multiselect("Choose skills", sorted(labels, key=lambda skill: labels[skill].casefold()),
                default=[s for s in ["databricks", "microsoft fabric", "power bi", "dbt", "spark", "a/b testing"] if s in labels],
                format_func=labels.get)
            st.caption("This is a personal watchlist, not a market ranking. Zero means no matched mention in the available title and snippet text.")
            st.dataframe(summary[summary.skill.isin(watched)][columns].round(2), hide_index=True, width="stretch")
        choice = st.selectbox("Skill trend", summary.skill.tolist(), format_func=labels.get)
        trend = daily[daily.skill == choice].rename(columns={
            "extract_date": "Date", "groups_with_mention": "Groups with mention", "observed_groups": "Observed groups"})
        trend["Share (%)"] = trend["Groups with mention"] / trend["Observed groups"] * 100
        trend_figure = px.line(
            trend,
            x="Date",
            y="Share (%)",
            markers=True,
            custom_data=["Groups with mention", "Observed groups"],
            title=f"{labels[choice]} in observed groups",
            color_discrete_sequence=["#2563eb"],
        )
        trend_figure.update_traces(
            line_width=2,
            marker_size=8,
            connectgaps=False,
            hovertemplate=(
                "<b>%{x}</b><br>Share: %{y:.1f}%"
                "<br>Groups with mention: %{customdata[0]}"
                "<br>Observed groups: %{customdata[1]}<extra></extra>"
            ),
        )
        trend_figure.update_layout(margin=dict(l=10, r=10, t=55, b=10))
        trend_figure.update_yaxes(rangemode="tozero", ticksuffix="%")
        st.plotly_chart(trend_figure, width="stretch", config=PLOTLY_CONFIG)
        st.caption("Each point is an observed date. Missing dates are not plotted as zero. A skill can be zero on an observed date.")
        with st.expander("All tracked skills"):
            st.dataframe(summary[columns].round(2), hide_index=True, width="stretch")

with explore_tab:
    st.subheader("Inspect the selected snapshot")
    search = st.text_input("Search postings", placeholder="Job title, company or location")
    if search.strip():
        mask = pd.Series(False, index=posts.index)
        for column in ["job_title", "company_name", "location"]:
            mask |= posts[column].str.contains(search.strip(), case=False, na=False, regex=False)
        posts = posts[mask]
    st.caption(
        f"Showing {min(100, len(posts))} of {len(posts):,} matching postings, newest source date first. "
        "These adverts were observed in the selected snapshot, but the dashboard does not verify whether a vacancy is still open."
    )
    if posts.empty:
        st.info("No postings match this search.")
    else:
        table = posts[["job_title", "company_name", "location", "posted_date", "redirect_url"]].rename(columns={
            "job_title": "Job title", "company_name": "Company", "location": "Location", "posted_date": "Posted date", "redirect_url": "Source page"})
        st.dataframe(table.head(100), hide_index=True, width="stretch",
            column_config={"Source page": st.column_config.LinkColumn("Source page", display_text="View source")})
        st.caption("Posted dates come from the source. A working source link is not confirmation that the vacancy remains active.")

with quality_tab:
    st.subheader("Selected snapshot quality signals")
    quality_count = int(quality.source_postings)
    missing_companies = int(quality.missing_companies)
    likely_truncated = int(quality.likely_truncated)
    salaries_available = int(quality.salaries_available)
    stale_postings = int(quality.stale_postings)
    training_postings = int(quality.training_postings)
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Unknown companies", f"{missing_companies:,}", help="The source company name was missing; raw data remains unchanged.")
    q2.metric("Likely truncated snippets", f"{likely_truncated:,}", help="Descriptions at the observed 500-character API boundary.")
    q3.metric("Postings with salary", f"{salaries_available:,}", help="At least one positive salary bound is available.")
    q4.metric("Older than 90 days", f"{stale_postings:,}", help="Age is measured at the selected observation date; it does not prove closure.")
    st.caption(
        f"{training_postings:,} source postings are conservatively flagged from their titles as training, "
        "internship or placement-style adverts. They remain in the sample."
    )
    salary_share = salaries_available / quality_count if quality_count else 0
    inferred_currency = int(quality.inferred_currency)
    st.caption(
        f"Salary coverage is {salary_share:.1%}. For {inferred_currency:,} postings with usable salary data, "
        "currency is inferred from the search country (EUR for Germany, GBP for the UK) and kept separate from source-provided currency."
    )
    st.subheader("Repeated posting groups")
    st.caption("Selected snapshot. Matching text can identify repeated adverts but can also combine separate vacancies. Training and placement adverts have not been excluded.")
    st.dataframe(repeated[["company", "title", "source_postings", "locations"]].rename(columns={
        "company": "Company", "title": "Title", "source_postings": "Source postings", "locations": "Locations"}),
        hide_index=True, width="stretch")
    st.subheader("Observed collection coverage")
    st.dataframe(coverage[["extract_date", "search_country", "search_role", "source_postings"]].rename(
        columns={"source_postings": "Source postings"}), hide_index=True, width="stretch")
    st.caption("This table shows database observations, not extraction-status verification. A missing segment is unknown, not zero. Status-file integration is a separate follow-up.")
