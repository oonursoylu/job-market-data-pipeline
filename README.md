# Job Market Data Pipeline

> Status: Active development. This is a portfolio data engineering project built step by step to practice API ingestion, raw data archiving, PostgreSQL loading, dbt modeling, data quality checks, and analytics reporting.

## Project Overview

This project collects Data and AI job postings from the Adzuna API, archives the raw JSON responses locally, loads the data into PostgreSQL, and models it with dbt for later analysis and dashboarding.

The project started with Germany to keep the first version focused. After validating the raw ingestion and load design, the pipeline was expanded to include the United Kingdom for country-level comparison.

Current scope:

- Countries: Germany (`de`) and United Kingdom (`gb`)
- Roles: Data Engineer, Analytics Engineer, AI Engineer
- Collection depth: 3 pages per role and country, 50 records per page
- Source: Adzuna API
- Raw archive format: local JSONL files
- Database: PostgreSQL
- Transformation layer: dbt Core

## Why This Project

The goal is to build a small but realistic recurring batch data pipeline instead of working only with a static dataset.

The project is designed to demonstrate practical data engineering patterns:

- extracting data from an external API
- preserving raw API responses
- loading data into a relational database
- handling duplicates safely
- separating raw job entities from daily search observations
- validating source freshness and data quality with dbt
- preparing the data for market insights such as role demand and skill demand

## Why Germany First

Germany was the initial focus because it keeps the project scope manageable while staying close to the target job market. Starting with one country made it easier to validate the ingestion logic, raw archive design, database schema, duplicate handling, and dbt setup before expanding to another market.

The United Kingdom was added after the first raw pipeline was working, which allows future Germany vs UK comparisons without changing the core pipeline design.

## Why PostgreSQL

PostgreSQL is used as the main database because it supports practical data engineering patterns such as raw data storage, JSONB columns, duplicate handling, indexing, constraints, backups, and exports.

It also keeps the project local, reproducible, and sustainable without relying on cloud trials or billing. If the project later adds semantic search or RAG, PostgreSQL can also be extended with `pgvector`.

## Current Pipeline

```text
Adzuna API
-> Python ingestion
-> Local JSONL raw archive
-> PostgreSQL raw schema
-> dbt sources and staging models
-> dbt tests and freshness checks
-> dbt marts, dashboard, and reports (planned)
```

The current working pipeline supports:

- fetching real job postings from the Adzuna API
- collecting data for Germany and the UK
- running extracts for Data Engineer, Analytics Engineer, and AI Engineer roles
- writing raw API job records to local JSONL archive files
- reading JSONL archive files back into Python
- mapping Adzuna job fields into PostgreSQL table columns
- loading records into PostgreSQL
- keeping unique job postings in PostgreSQL with `ON CONFLICT DO NOTHING`
- recording country, role, and date level sightings in `raw.job_posting_observations`
- defining raw PostgreSQL tables as dbt sources
- running dbt source freshness checks
- building dbt staging views
- testing staging models with dbt generic tests

## Latest Verified Local Snapshot

As of 2026-06-17, the latest verified local snapshot contains:

```text
raw.job_postings: 1,032 unique job postings
raw.job_posting_observations: 2,100 observations
```

Observation coverage for 2026-06-17:

```text
de / data_engineer: 150
de / analytics_engineer: 150
de / ai_engineer: 150
gb / data_engineer: 150
gb / analytics_engineer: 150
gb / ai_engineer: 150
```

Latest dbt validation:

```text
dbt build: 33 checks passed, 0 warnings, 0 errors
```

These numbers are a local development snapshot and will change as the pipeline is run on later dates.

## PostgreSQL Raw Design

The raw layer contains two main tables:

```text
raw.job_postings
raw.job_posting_observations
```

`raw.job_postings` stores one row per unique source job posting. Duplicate jobs are skipped with a database constraint and `ON CONFLICT DO NOTHING`.

`raw.job_posting_observations` stores when a job posting was seen for a specific country, role, and extraction date. This separates the job entity from the search event and makes the pipeline safer to rerun.

This design supports two important use cases:

- keeping a unique job posting catalog
- building time-series demand signals from repeated observations

## dbt Layer

The first dbt layer has been added on top of the PostgreSQL raw schema.

Implemented so far:

- dbt project setup with PostgreSQL connection
- source definitions for:
  - `raw.job_postings`
  - `raw.job_posting_observations`
- source freshness checks using:
  - `loaded_at` for job postings
  - `observed_at` for observations
- staging models:
  - `stg_job_postings`
  - `stg_job_posting_observations`
- generic dbt tests:
  - `not_null`
  - `unique`
  - `accepted_values`
  - `relationships`

The staging layer currently preserves the raw grain while cleaning text fields, deriving a posting date, and making the observation grain explicit with a deterministic `observation_id`.

## Project Structure

```text
src/
  extract/
    adzuna_client.py
    archive_writer.py
    run_adzuna_extract.py
  load/
    jsonl_reader.py
    job_mapper.py
    postgres_loader.py
    run_postgres_load.py
  transform/
  reports/
  utils/
sql/
  001_create_raw_schema.sql
  002_raw_data_quality_checks.sql
dbt_job_market/
  models/
    staging/
  seeds/
  tests/
  macros/
data/
  raw/
reports/
  weekly/
docs/
  screenshots/
  linkedin_posts/
```

## Environment Variables

Create a local `.env` file based on `.env.example`.

Required values:

```text
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=job_market
POSTGRES_USER=job_market_user
POSTGRES_PASSWORD=
DEFAULT_COUNTRIES=de,gb
DEFAULT_RESULTS_PER_PAGE=50
DEFAULT_MAX_PAGES=3
```

The real `.env` file is ignored by Git.

The current ingestion scripts define the active country and pagination scope directly in the Python entry points. The ingestion default variables are kept as a planned parameterization point.

## How To Run

Run the extract step:

```powershell
python src\extract\run_adzuna_extract.py
```

Run the PostgreSQL load step:

```powershell
python src\load\run_postgres_load.py
```

Run dbt from the dbt project directory:

```powershell
cd dbt_job_market
dbt source freshness
dbt build
```

## Daily Manual Run Before Airflow

Airflow has not been added yet. Until orchestration is implemented, the pipeline can be run manually once per day:

```powershell
python src\extract\run_adzuna_extract.py
python src\load\run_postgres_load.py
cd dbt_job_market
dbt source freshness
dbt build
cd ..
```

The load step is designed to be safe to rerun. Existing job postings and duplicate same-day observations are skipped by database constraints.

## Useful Validation Queries

Check the raw table counts:

```powershell
@'
import sys

sys.path.append("src/load")

from postgres_loader import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM raw.job_postings")
print("raw.job_postings:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM raw.job_posting_observations")
print("raw.job_posting_observations:", cur.fetchone()[0])

cur.close()
conn.close()
'@ | python -
```

Check today's observation counts by country and role:

```powershell
@'
import sys

sys.path.append("src/load")

from postgres_loader import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("""
    SELECT search_country, search_role, extract_date, COUNT(*)
    FROM raw.job_posting_observations
    WHERE extract_date = CURRENT_DATE
    GROUP BY search_country, search_role, extract_date
    ORDER BY search_country, search_role
""")

for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
'@ | python -
```

## Next Steps

- continue daily manual ingestion before Airflow
- add a skill dictionary seed for lightweight skill extraction
- build intermediate dbt models for job-skill mapping
- build mart tables for country, role, skill, location, and company analysis
- create a Streamlit dashboard
- generate a weekly Markdown market report
- add Airflow orchestration
- add Docker Compose later for reproducibility

## Limitations

- The Adzuna API may not represent the full job market.
- Salary information is often missing or incomplete in job postings.
- The first skill extraction layer will be dictionary-based and may miss some skills or create false positives.
- The project is an active portfolio project, not a production deployment.
- Missed ingestion days are not backfilled with synthetic observations.

## Future Improvements

- UK comparison dashboards
- more role categories
- more robust skill extraction with NLP
- LLM-assisted weekly report generation
- PostgreSQL `pgvector` based semantic search
- Docker Compose setup
- Airflow orchestration
- CI checks for dbt build
