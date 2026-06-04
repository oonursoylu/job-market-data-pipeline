# Germany Job Market Data Pipeline

A Germany-first portfolio data engineering project for collecting, archiving, loading, modeling, and analyzing job postings using Python, PostgreSQL, dbt, Airflow, and Streamlit.

## Project Goal

The goal of this project is to build a recurring batch data pipeline that collects job postings from an external API, stores raw data locally and in PostgreSQL, models the data with dbt, applies data quality checks, and presents market insights through a dashboard and weekly reports.

The project starts with Germany and a small set of data-focused roles:

- Data Engineer
- Analytics Engineer
- AI Engineer

## Why Germany First?

Germany is the initial focus because it keeps the project scope manageable while staying close to the target job market. Starting with one country makes it easier to validate the ingestion logic, raw archive design, database schema, dbt models, and dashboard before expanding to other markets.

## Why PostgreSQL?

PostgreSQL is used as the main database because it supports practical data engineering patterns such as raw data storage, JSONB columns, duplicate handling, indexing, backups, and exports. It also keeps the project local, reproducible, and sustainable without relying on cloud trials or billing.

## Current MVP Pipeline

The current working MVP covers the raw ingestion and loading layer:

```text
Adzuna API
-> Python extract script
-> Local JSONL raw archive
-> PostgreSQL raw.job_postings table
-> PostgreSQL raw.job_posting_observations table
```

The MVP currently supports:

- fetching real job postings from the Adzuna API
- running extract jobs for Data Engineer, Analytics Engineer, and AI Engineer roles
- writing raw API job records to local JSONL archive files
- reading JSONL archive files back into Python
- mapping Adzuna job fields into PostgreSQL table columns
- loading records into PostgreSQL
- keeping unique job postings in PostgreSQL with `ON CONFLICT DO NOTHING`
- recording daily role-level sightings in `raw.job_posting_observations`

## Current Validation

The MVP has been tested with multi-role extracts and PostgreSQL loads:

```text
Country: Germany
Search roles: data_engineer, analytics_engineer, ai_engineer
Pages fetched: 2
Results per page: 50
Extract date: 2026-06-04
JSONL records written per role: 100
Total JSONL records written: 300
PostgreSQL records before multi-role load: 100
New PostgreSQL records inserted: 206
Duplicate records skipped: 94
PostgreSQL records after multi-role load: 306
Job posting observations inserted: 300
Duplicate observation reload result: 0 inserted, 300 skipped
```

The `raw.job_postings` table behaves as a unique job posting store. Duplicate Adzuna jobs are skipped based on `(source, job_id)`. The `raw.job_posting_observations` table records daily role-level sightings based on `(source, job_id, search_country, search_role, extract_date)`.

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
DEFAULT_COUNTRY=de
DEFAULT_RESULTS_PER_PAGE=50
DEFAULT_MAX_PAGES=2
```

The real `.env` file is ignored by Git.

## How To Run

Run the extract step:

```powershell
python src\extract\run_adzuna_extract.py
```

Run the PostgreSQL load step:

```powershell
python src\load\run_postgres_load.py
```

Check the raw table count:

```powershell
python -c "from src.load.postgres_loader import get_connection; conn = get_connection(); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM raw.job_postings'); print(cur.fetchone()[0]); cur.close(); conn.close()"
```

Check the raw observation table count:

```powershell
python -c "from src.load.postgres_loader import get_connection; conn = get_connection(); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM raw.job_posting_observations'); print(cur.fetchone()[0]); cur.close(); conn.close()"
```

## Planned Pipeline Flow

```text
Adzuna API
-> Python ingestion
-> Local JSONL raw archive
-> PostgreSQL raw schema
-> dbt staging, intermediate, and mart models
-> data quality and freshness checks
-> Airflow orchestration
-> Streamlit dashboard
-> weekly Markdown report
```

## Next Steps

- parameterize country, role, date, page count, and results per page
- add dbt staging models on top of `raw.job_postings`
- add data quality and freshness checks
- add Airflow orchestration
- build Streamlit dashboard
- generate weekly Markdown reports

## Project Status

Current stage: working multi-role MVP raw ingestion, PostgreSQL unique posting load, and observation load completed.
