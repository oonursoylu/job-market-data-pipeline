import os

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
from dotenv import load_dotenv


load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


@st.cache_data(ttl=300)
def load_overview_metrics():
    query = """
        select
            count(*) as source_postings,
            count(distinct posting_group_id) as deduped_posting_groups,
            count(*) - count(distinct posting_group_id) as estimated_inflation,
            max(latest_extract_date) as latest_extract_date
        from analytics.mart_latest_postings
    """

    with get_connection() as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=300)
def load_role_demand():
    query = """
        select
            extract_date,
            search_country,
            search_role,
            observed_posting_count,
            deduped_posting_group_count,
            observed_posting_count - deduped_posting_group_count as estimated_inflation,
            round(
                100.0 * (observed_posting_count - deduped_posting_group_count)
                / nullif(observed_posting_count, 0),
                1
            ) as inflation_pct
        from analytics.fct_role_demand_daily
        where extract_date = (
            select max(extract_date)
            from analytics.fct_role_demand_daily
        )
        order by estimated_inflation desc
    """

    with get_connection() as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=300)
def load_top_multilocation_groups():
    query = """
        with latest_observations as (

            select
                source,
                job_id,
                search_country,
                search_role,
                extract_date

            from analytics.stg_job_posting_observations

            where extract_date = (
                select max(extract_date)
                from analytics.stg_job_posting_observations
            )

        ),

        joined as (

            select
                latest_observations.search_country,
                latest_observations.search_role,
                posting_groups.posting_group_id,
                posting_groups.normalized_company_name,
                posting_groups.normalized_job_title,
                posting_groups.location,
                latest_observations.job_id

            from latest_observations
            inner join analytics.int_job_posting_groups as posting_groups
                on latest_observations.source = posting_groups.source
                and latest_observations.job_id = posting_groups.job_id

        )

        select
            search_country,
            search_role,
            normalized_company_name,
            normalized_job_title,
            count(distinct job_id) as source_job_count,
            count(distinct location) as location_count

        from joined

        group by
            search_country,
            search_role,
            posting_group_id,
            normalized_company_name,
            normalized_job_title

        having count(distinct job_id) > 1

        order by source_job_count desc, location_count desc

        limit 10
    """

    with get_connection() as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=300)
def load_skill_demand_daily():
    query = """
        select
            extract_date,
            search_country,
            search_role,
            skill,
            category,
            deduped_posting_group_count
        from analytics.fct_skill_demand_daily
        order by extract_date, search_country, search_role, skill
    """

    with get_connection() as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=300)
def load_complete_extract_dates():
    query = """
        with daily_coverage as (

            select
                extract_date,
                count(distinct search_country || '/' || search_role) as country_role_segments

            from analytics.stg_job_posting_observations

            group by extract_date

        ),

        expected_coverage as (

            select
                max(country_role_segments) as expected_country_role_segments

            from daily_coverage

        )

        select
            daily_coverage.extract_date

        from daily_coverage
        cross join expected_coverage

        where daily_coverage.country_role_segments = expected_coverage.expected_country_role_segments

        order by daily_coverage.extract_date
    """

    with get_connection() as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=300)
def load_latest_postings():
    query = """
        select
            job_title,
            company_name,
            location,
            search_country,
            search_role,
            posted_date,
            first_observed_date,
            latest_extract_date,
            times_observed,
            redirect_url
        from analytics.mart_latest_postings
        order by latest_extract_date desc, times_observed desc, company_name, job_title
    """

    with get_connection() as conn:
        return pd.read_sql(query, conn)


COUNTRY_LABELS = {
    "de": "Germany",
    "gb": "United Kingdom",
}

ROLE_LABELS = {
    "data_engineer": "Data Engineer",
    "analytics_engineer": "Analytics Engineer",
    "ai_engineer": "AI Engineer",
}

COUNTRY_CODES = {label: code for code, label in COUNTRY_LABELS.items()}
ROLE_CODES = {label: code for code, label in ROLE_LABELS.items()}

SKILL_LABELS = {
    "aws": "AWS",
    "gcp": "GCP",
    "sql": "SQL",
    "dbt": "dbt",
    "power bi": "Power BI",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mlflow": "MLflow",
}

CATEGORY_LABELS = {
    "ai": "AI",
    "bi": "BI",
    "big_data": "Big Data",
    "cloud": "Cloud",
    "database": "Database",
    "devops": "DevOps",
    "mlops": "MLOps",
    "orchestration": "Orchestration",
    "programming": "Programming",
    "transformation": "Transformation",
    "warehouse": "Warehouse",
}


def format_skill_label(skill):
    return SKILL_LABELS.get(skill, str(skill).title())


st.set_page_config(
    page_title="Job Market Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)

st.title("Job Market Dashboard")

overview = load_overview_metrics().iloc[0]
latest_extract_date = pd.to_datetime(overview["latest_extract_date"]).date()

st.caption(f"Latest extract date: {latest_extract_date}")

col1, col2, col3 = st.columns(3)

col1.metric(
    label="Source postings",
    value=f"{overview['source_postings']:,}",
)

col2.metric(
    label="Estimated opportunities",
    value=f"{overview['deduped_posting_groups']:,}",
)

col3.metric(
    label="Potential multi-location inflation",
    value=f"{overview['estimated_inflation']:,}",
)

st.divider()

st.write(
    "The dashboard compares source-level job postings with deduplicated analytical posting groups. "
    "Deduplicated counts reduce inflation from multi-location postings."
)

st.subheader("Role Demand")

role_demand = load_role_demand()

role_demand["country"] = role_demand["search_country"].map(COUNTRY_LABELS)
role_demand["role"] = role_demand["search_role"].map(ROLE_LABELS)
role_demand["segment"] = role_demand["country"] + " / " + role_demand["role"]

role_chart_data = role_demand.melt(
    id_vars=["segment"],
    value_vars=["observed_posting_count", "deduped_posting_group_count"],
    var_name="metric",
    value_name="posting_count",
)

role_chart_data["metric"] = role_chart_data["metric"].replace(
    {
        "observed_posting_count": "Source postings",
        "deduped_posting_group_count": "Estimated opportunities",
    }
)

fig = px.bar(
    role_chart_data,
    x="segment",
    y="posting_count",
    color="metric",
    barmode="group",
    labels={
        "segment": "Country / Role",
        "posting_count": "Postings",
        "metric": "Metric",
    },
)

st.plotly_chart(fig, use_container_width=True)

role_demand_table = role_demand[
    [
        "country",
        "role",
        "observed_posting_count",
        "deduped_posting_group_count",
        "estimated_inflation",
        "inflation_pct",
    ]
].rename(
    columns={
        "country": "Country",
        "role": "Role",
        "observed_posting_count": "Source postings",
        "deduped_posting_group_count": "Estimated opportunities",
        "estimated_inflation": "Estimated inflation",
        "inflation_pct": "Inflation %",
    }
)
role_demand_table["Inflation %"] = role_demand_table["Inflation %"].round(1)

st.dataframe(
    role_demand_table,
    use_container_width=True,
    hide_index=True,
)

st.subheader("Top Multi-Location Posting Groups")

st.caption(
    "These groups show source postings that likely represent the same role repeated across multiple locations."
)

multi_location_groups = load_top_multilocation_groups()

multi_location_groups["Country"] = multi_location_groups["search_country"].map(COUNTRY_LABELS)
multi_location_groups["Role"] = multi_location_groups["search_role"].map(ROLE_LABELS)
multi_location_groups["Company"] = multi_location_groups["normalized_company_name"].str.title()
multi_location_groups["Title"] = multi_location_groups["normalized_job_title"].str.title()

multi_location_table = multi_location_groups[
    [
        "Country",
        "Role",
        "Company",
        "Title",
        "source_job_count",
        "location_count",
    ]
].rename(
    columns={
        "source_job_count": "Source postings",
        "location_count": "Locations",
    }
)

st.dataframe(
    multi_location_table,
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader("Skill Demand")

st.caption(
    "Skill demand is aggregated from daily deduplicated posting group counts, so repeated multi-location postings do not inflate the main ranking."
)

skill_demand_daily = load_skill_demand_daily()
complete_extract_dates = load_complete_extract_dates()

skill_demand_daily["extract_date"] = pd.to_datetime(skill_demand_daily["extract_date"])
complete_extract_dates["extract_date"] = pd.to_datetime(complete_extract_dates["extract_date"])
skill_demand_daily = skill_demand_daily[
    skill_demand_daily["extract_date"].isin(complete_extract_dates["extract_date"])
]
skill_demand_daily["Country"] = skill_demand_daily["search_country"].map(COUNTRY_LABELS)
skill_demand_daily["Role"] = skill_demand_daily["search_role"].map(ROLE_LABELS)
skill_demand_daily["Skill"] = skill_demand_daily["skill"].map(format_skill_label)
skill_demand_daily["Category"] = skill_demand_daily["category"].map(CATEGORY_LABELS)

if not complete_extract_dates.empty:
    first_complete_extract_date = complete_extract_dates["extract_date"].min().date()
    st.caption(
        "Skill demand uses complete extraction dates only, where all country and role segments were collected. "
        f"The comparable trend window starts on {first_complete_extract_date}."
    )

filter_col1, filter_col2, filter_col3 = st.columns(3)

selected_country = filter_col1.selectbox(
    "Country",
    ["All", *COUNTRY_CODES.keys()],
)

selected_role = filter_col2.selectbox(
    "Role",
    ["All", *ROLE_CODES.keys()],
)

selected_window = filter_col3.selectbox(
    "Time window",
    ["Last 30 days", "All available data"],
)

st.caption(
    f"Filters: Country = {selected_country} | Role = {selected_role} | Time window = {selected_window}"
)

filtered_skill_demand = skill_demand_daily.copy()

if selected_country != "All":
    filtered_skill_demand = filtered_skill_demand[
        filtered_skill_demand["search_country"] == COUNTRY_CODES[selected_country]
    ]

if selected_role != "All":
    filtered_skill_demand = filtered_skill_demand[
        filtered_skill_demand["search_role"] == ROLE_CODES[selected_role]
    ]

if selected_window == "Last 30 days" and not filtered_skill_demand.empty:
    latest_skill_date = filtered_skill_demand["extract_date"].max()
    window_start_date = latest_skill_date - pd.Timedelta(days=30)
    filtered_skill_demand = filtered_skill_demand[
        filtered_skill_demand["extract_date"] >= window_start_date
    ]

if filtered_skill_demand.empty:
    st.warning("No skill demand data is available for the selected filters.")
else:
    skill_summary = (
        filtered_skill_demand.groupby(["Skill", "Category"], as_index=False)
        .agg(
            total_skill_mentions=("deduped_posting_group_count", "sum"),
            active_run_days=("extract_date", "nunique"),
            avg_mentions_per_run=("deduped_posting_group_count", "mean"),
            latest_extract_date=("extract_date", "max"),
        )
        .sort_values("total_skill_mentions", ascending=False)
        .head(10)
    )
    skill_summary["avg_mentions_per_run"] = skill_summary["avg_mentions_per_run"].round(2)
    skill_summary["latest_extract_date"] = pd.to_datetime(
        skill_summary["latest_extract_date"]
    ).dt.date

    skill_chart = px.bar(
        skill_summary.sort_values("total_skill_mentions"),
        x="total_skill_mentions",
        y="Skill",
        color="Category",
        orientation="h",
        labels={
            "total_skill_mentions": "Deduplicated skill mentions",
            "Skill": "Skill",
            "Category": "Category",
        },
    )
    skill_chart.update_layout(legend_title_text="Category")

    st.plotly_chart(skill_chart, use_container_width=True)

    skill_demand_table = skill_summary.rename(
        columns={
            "total_skill_mentions": "Deduplicated skill mentions",
            "active_run_days": "Active run days",
            "avg_mentions_per_run": "Avg mentions per run",
            "latest_extract_date": "Latest extract date",
        }
    )

    st.dataframe(
        skill_demand_table,
        use_container_width=True,
        hide_index=True,
    )

    selected_skill = st.selectbox(
        "Skill trend",
        skill_summary["Skill"].tolist(),
    )

    skill_trend = (
        filtered_skill_demand[filtered_skill_demand["Skill"] == selected_skill]
        .groupby("extract_date", as_index=False)
        .agg(deduped_posting_groups=("deduped_posting_group_count", "sum"))
        .sort_values("extract_date")
    )

    trend_chart = px.line(
        skill_trend,
        x="extract_date",
        y="deduped_posting_groups",
        markers=True,
        labels={
            "extract_date": "Extract date",
            "deduped_posting_groups": "Deduplicated posting groups",
        },
    )
    trend_chart.update_layout(title=f"{selected_skill} Demand Trend")

    st.plotly_chart(trend_chart, use_container_width=True)

st.divider()

st.subheader("Latest Postings")

st.caption(
    "Latest observed source postings. Use this table to inspect example jobs behind the aggregate metrics."
)

latest_postings = load_latest_postings()
latest_postings["Country"] = latest_postings["search_country"].map(COUNTRY_LABELS)
latest_postings["Role"] = latest_postings["search_role"].map(ROLE_LABELS)
latest_postings["Posted date"] = pd.to_datetime(latest_postings["posted_date"]).dt.date
latest_postings["First observed"] = pd.to_datetime(
    latest_postings["first_observed_date"]
).dt.date
latest_postings["Latest observed"] = pd.to_datetime(
    latest_postings["latest_extract_date"]
).dt.date

posting_filter_col1, posting_filter_col2, posting_filter_col3 = st.columns([1, 1, 2])

selected_posting_country = posting_filter_col1.selectbox(
    "Posting country",
    ["All", *COUNTRY_CODES.keys()],
)

selected_posting_role = posting_filter_col2.selectbox(
    "Posting role",
    ["All", *ROLE_CODES.keys()],
)

posting_search = posting_filter_col3.text_input(
    "Search postings",
    placeholder="Job title, company, or location",
)

filtered_postings = latest_postings.copy()

if selected_posting_country != "All":
    filtered_postings = filtered_postings[
        filtered_postings["search_country"] == COUNTRY_CODES[selected_posting_country]
    ]

if selected_posting_role != "All":
    filtered_postings = filtered_postings[
        filtered_postings["search_role"] == ROLE_CODES[selected_posting_role]
    ]

if posting_search.strip():
    search_text = posting_search.strip()
    filtered_postings = filtered_postings[
        filtered_postings["job_title"].str.contains(search_text, case=False, na=False, regex=False)
        | filtered_postings["company_name"].str.contains(search_text, case=False, na=False, regex=False)
        | filtered_postings["location"].str.contains(search_text, case=False, na=False, regex=False)
    ]

latest_postings_table = filtered_postings[
    [
        "Country",
        "Role",
        "job_title",
        "company_name",
        "location",
        "Posted date",
        "First observed",
        "Latest observed",
        "times_observed",
        "redirect_url",
    ]
].rename(
    columns={
        "job_title": "Job title",
        "company_name": "Company",
        "location": "Location",
        "times_observed": "Times observed",
        "redirect_url": "URL",
    }
)

st.dataframe(
    latest_postings_table.head(100),
    use_container_width=True,
    hide_index=True,
    column_config={
        "URL": st.column_config.LinkColumn("Posting", display_text="Open"),
        "Times observed": st.column_config.NumberColumn("Times observed", format="%d"),
    },
)
