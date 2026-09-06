import os

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
from dotenv import load_dotenv


load_dotenv()
COUNTRIES = {"de": "Germany", "gb": "United Kingdom"}
ROLES = {
    "data_engineer": "Data Engineer",
    "analytics_engineer": "Analytics Engineer",
    "ai_engineer": "AI Engineer",
}
LABELS = {
    "sql": "SQL", "aws": "AWS", "gcp": "GCP", "dbt": "dbt",
    "power bi": "Power BI", "dax": "DAX", "postgresql": "PostgreSQL",
    "mysql": "MySQL", "mongodb": "MongoDB", "mlflow": "MLflow",
    "a/b testing": "A/B Testing", "ci/cd": "CI/CD", "etl/elt": "ETL / ELT",
    "llm": "LLM", "numpy": "NumPy", "scikit-learn": "scikit-learn",
}


def skill_label(value):
    return LABELS.get(value, str(value).title())


def read_frame(connection, query):
    with connection.cursor() as cursor:
        cursor.execute(query)
        return pd.DataFrame(cursor.fetchall(), columns=[item[0] for item in cursor.description])


@st.cache_data(ttl=300)
def load_data():
    connection = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"), connect_timeout=5,
    )
    try:
        connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with connection.cursor() as cursor:
            cursor.execute("SET statement_timeout = 20000")
        observations = read_frame(connection, """
            select o.source, o.job_id, o.search_country, o.search_role, o.extract_date,
                   g.posting_group_id, p.job_title, p.company_name, p.location,
                   p.posted_date, p.redirect_url
            from analytics.stg_job_posting_observations o
            join analytics.stg_job_postings p using (source, job_id)
            join analytics.int_job_posting_groups g using (source, job_id)
            where o.search_country in ('de', 'gb')
              and o.search_role in ('data_engineer', 'analytics_engineer', 'ai_engineer')
        """)
        skills = read_frame(connection, """
            select source, job_id, skill, category
            from analytics.int_job_posting_skills
        """)
        dictionary = read_frame(connection, "select skill, category from analytics.skill_dictionary")
        return observations, skills, dictionary
    finally:
        connection.rollback()
        connection.close()


def scope_rows(frame, countries, roles):
    return frame[frame.search_country.isin(countries) & frame.search_role.isin(roles)].copy()


def group_count(frame):
    return frame.posting_group_id.nunique()


def skill_metrics(observations, skills, dictionary, countries, roles, start, end):
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


st.set_page_config(page_title="Job Market Explorer", page_icon="📊", layout="wide")
st.title("Job Market Explorer")
st.caption("Explore collected job adverts, skill mentions and repeated posting groups.")
with st.sidebar:
    st.header("Scope")
    countries = st.multiselect("Countries", list(COUNTRIES), default=list(COUNTRIES), format_func=COUNTRIES.get)
    roles = st.multiselect("Search roles", list(ROLES), default=list(ROLES), format_func=ROLES.get)
    if st.button("Refresh data"):
        load_data.clear()
    st.caption("Data Analyst is being archived separately and is not included yet.")
if not countries or not roles:
    st.info("Select at least one country and search role.")
    st.stop()
try:
    observations, skills, dictionary = load_data()
except Exception:
    st.error("Could not load data. Check that PostgreSQL is running and the dbt models are available.")
    st.stop()
if observations.empty:
    st.info("No observations are available yet.")
    st.stop()
observations["extract_date"] = pd.to_datetime(observations.extract_date).dt.date
scoped = scope_rows(observations, countries, roles)
if scoped.empty:
    st.info("No observations match this scope.")
    st.stop()
available_dates = sorted(scoped.extract_date.unique(), reverse=True)
snapshot_date = st.sidebar.selectbox("Snapshot date", available_dates)
snapshot = scoped[scoped.extract_date == snapshot_date]
st.caption(f"Snapshot: {snapshot_date} | {len(countries)} countries · {len(roles)} search roles | Skills has its own date window.")
with st.expander("How to read this dashboard"):
    st.write("One API source, with up to 150 results per country and search role in each collection. Counts describe this sample, not total market demand. Search roles can overlap.")
    st.write("Analytical groups match normalised company, title and description within each country and source. They are not verified vacancies. Reposts and similar separate jobs may share a group.")
    st.write("Skills are matched in short description snippets, at most 500 characters in the current archive. A missing mention is not evidence that a skill is unnecessary. Historical snippets are rescored when the dictionary changes.")

overview_tab, skills_tab, explore_tab, quality_tab = st.tabs(["Overview", "Skills", "Explore Postings", "Data Quality"])
with overview_tab:
    st.subheader("Skills in the selected snapshot")
    snapshot_summary, _, snapshot_denominator = skill_metrics(
        observations, skills, dictionary, countries, roles, snapshot_date, snapshot_date
    )
    if snapshot_summary.empty:
        st.info("Skill comparison is unavailable: some selected country/role segments have no observations on this date.")
    else:
        st.caption("Share of analytical groups with a skill mention on this date. Each group counts once across selected roles. A group can mention several skills.")
        ranking_column, watch_column = st.columns([3, 2])
        with ranking_column:
            st.write("**Most mentioned skills**")
            snapshot_top = snapshot_summary[snapshot_summary["Group-days with mention"] > 0].head(10)
            if snapshot_top.empty:
                st.info("No tracked skill mentions found in this snapshot.")
            else:
                snapshot_top = snapshot_top.rename(columns={"Share of observed group-days (%)": "Share of groups (%)"})
                st.plotly_chart(px.bar(snapshot_top.sort_values("Share of groups (%)"),
                    x="Share of groups (%)", y="Skill", orientation="h",
                    color_discrete_sequence=["#2563eb"]), width="stretch", key="snapshot_top_skills")
        with watch_column:
            st.write("**Skills to watch**")
            focus = ["databricks", "microsoft fabric", "power bi", "dbt", "spark", "a/b testing"]
            watch = snapshot_summary[snapshot_summary.skill.isin(focus)].copy()
            watch = watch.set_index("skill").reindex([s for s in focus if s in watch.skill.values])
            watch = watch.rename(columns={"Group-days with mention": "Groups", "Share of observed group-days (%)": "Share (%)"})
            st.dataframe(watch[["Skill", "Groups", "Share (%)"]].round(2), hide_index=True, width="stretch")
            st.caption("A personal watchlist. Zero means no matched mention in the available snippets.")
            st.write("Open **Skills** for all 53 tracked skills, a custom watchlist and trends.")
    st.subheader("Selected snapshot")
    source_count = len(snapshot.drop_duplicates(["source", "job_id"]))
    groups = group_count(snapshot)
    reduction = source_count - groups
    a, b, c = st.columns(3)
    a.metric("Source postings", f"{source_count:,}")
    b.metric("Analytical groups", f"{groups:,}")
    c.metric("Fewer entries after grouping", f"{reduction:,}", help="Source count minus group count. Not a confirmed duplicate count.")
    st.caption(f"{source_count:,} source postings become {groups:,} groups. Counts fall by {reduction / source_count:.1%}; this does not prove that the difference consists of duplicate vacancies.")
    by_role = snapshot.groupby(["search_country", "search_role"]).agg(
        source_postings=("job_id", "nunique"), analytical_groups=("posting_group_id", "nunique")
    ).reset_index()
    by_role["Segment"] = by_role.search_country.map(COUNTRIES) + " / " + by_role.search_role.map(ROLES)
    by_role["Reduction (%)"] = (1 - by_role.analytical_groups / by_role.source_postings) * 100
    chart = by_role.rename(columns={"source_postings": "Source postings", "analytical_groups": "Analytical groups"})
    melted = chart.melt(id_vars="Segment", value_vars=["Source postings", "Analytical groups"], var_name="Measure", value_name="Count")
    st.plotly_chart(px.bar(melted, x="Segment", y="Count", color="Measure", barmode="group",
        color_discrete_map={"Source postings": "#94a3b8", "Analytical groups": "#2563eb"}), width="stretch")
    st.caption("Segment counts may overlap. The cards count source IDs and groups once across the selected snapshot.")
    st.dataframe(chart[["Segment", "Source postings", "Analytical groups", "Reduction (%)"]].round(1), hide_index=True, width="stretch")
    with st.expander("Accumulated archive for this scope"):
        st.write(f"{len(scoped.drop_duplicates(['source', 'job_id'])):,} distinct source postings across {scoped.extract_date.nunique()} observed dates. These are not all currently open jobs.")

with skills_tab:
    st.subheader("Which skills appear in the sample?")
    window = st.radio("Skill window", ["Last 30 calendar days", "All observed dates"], horizontal=True)
    end = snapshot_date
    start = (pd.Timestamp(end) - pd.Timedelta(days=29)).date() if window.startswith("Last") else min(available_dates)
    summary, daily, denominator = skill_metrics(observations, skills, dictionary, countries, roles, start, end)
    st.caption(f"Window: {start} to {end}. Only dates with observations in every selected country/role segment are included. This does not prove that every API page completed.")
    if summary.empty:
        st.info("No dates have observations in every selected segment. Try a wider window or fewer segments.")
    else:
        st.caption(f"{len(denominator)} included dates · {int(denominator.sum()):,} observed group-days. A group counts once per date across selected roles. The same group can count on different dates.")
        st.write("**Top skills in the collected data**")
        top = summary[summary["Group-days with mention"] > 0].head(15)
        if top.empty:
            st.info("No tracked skill mentions were found in this scope.")
        else:
            st.plotly_chart(px.bar(top.sort_values("Share of observed group-days (%)"),
                x="Share of observed group-days (%)", y="Skill", orientation="h",
                color_discrete_sequence=["#2563eb"]), width="stretch")
        st.write("**Skills to watch**")
        watched = st.multiselect("Choose skills", dictionary.skill.tolist(),
            default=[s for s in ["databricks", "microsoft fabric", "power bi", "dbt", "spark", "a/b testing"] if s in dictionary.skill.values],
            format_func=skill_label)
        st.caption("This is a personal watchlist, not a market ranking. Zero means no matched mention in the available snippets.")
        columns = ["Skill", "Group-days with mention", "Share of observed group-days (%)", "Average groups per observed day"]
        st.dataframe(summary[summary.skill.isin(watched)][columns].round(2), hide_index=True, width="stretch")
        choice = st.selectbox("Skill trend", summary.skill.tolist(), format_func=skill_label)
        trend = pd.DataFrame({"Date": denominator.index, "Groups with mention": daily[choice].values,
                              "Observed groups": denominator.values})
        trend["Share (%)"] = trend["Groups with mention"] / trend["Observed groups"] * 100
        st.plotly_chart(px.scatter(trend, x="Date", y="Share (%)", hover_data=["Groups with mention", "Observed groups"],
            title=f"{skill_label(choice)} in observed groups", color_discrete_sequence=["#2563eb"]), width="stretch")
        st.caption("Each point is an observed date. Missing dates are not plotted as zero. A skill can be zero on an observed date.")
        with st.expander("All tracked skills"):
            st.dataframe(summary[columns].round(2), hide_index=True, width="stretch")

with explore_tab:
    st.subheader("Inspect the selected snapshot")
    search = st.text_input("Search postings", placeholder="Job title, company or location")
    posts = snapshot.sort_values(["source", "job_id", "search_role"]).drop_duplicates(["source", "job_id"])
    if search.strip():
        mask = pd.Series(False, index=posts.index)
        for column in ["job_title", "company_name", "location"]:
            mask |= posts[column].str.contains(search.strip(), case=False, na=False, regex=False)
        posts = posts[mask]
    st.caption(f"Showing {min(100, len(posts))} of {len(posts):,} matching postings. An observed advert may no longer be open.")
    if posts.empty:
        st.info("No postings match this search.")
    else:
        table = posts[["job_title", "company_name", "location", "posted_date", "redirect_url"]].rename(columns={
            "job_title": "Job title", "company_name": "Company", "location": "Location", "posted_date": "Posted date", "redirect_url": "URL"})
        st.dataframe(table.head(100), hide_index=True, width="stretch",
            column_config={"URL": st.column_config.LinkColumn("Advert", display_text="Open")})

with quality_tab:
    st.subheader("Repeated posting groups")
    repeated = snapshot.drop_duplicates(["source", "job_id"]).groupby("posting_group_id").agg(
        Company=("company_name", "first"), Title=("job_title", "first"),
        Source_postings=("job_id", "size"), Locations=("location", "nunique")
    ).reset_index()
    repeated = repeated[repeated.Source_postings > 1].sort_values("Source_postings", ascending=False)
    st.caption("Selected snapshot. Matching text can identify repeated adverts but can also combine separate vacancies. Training and placement adverts have not been excluded.")
    st.dataframe(repeated[["Company", "Title", "Source_postings", "Locations"]].rename(columns={"Source_postings": "Source postings"}).head(20), hide_index=True, width="stretch")
    st.subheader("Observed collection coverage")
    coverage = scoped.groupby(["extract_date", "search_country", "search_role"]).job_id.nunique().reset_index(name="Source postings")
    st.dataframe(coverage.sort_values(["extract_date", "search_country", "search_role"], ascending=[False, True, True]), hide_index=True, width="stretch")
    st.caption("This table shows database observations, not extraction-status verification. A missing segment is unknown, not zero. Status-file integration is a separate follow-up.")
