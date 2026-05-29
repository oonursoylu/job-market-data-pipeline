# Germany Job Market Data Pipeline

A Germany-first portfolio data engineering project for collecting, storing, modeling, and analyzing job postings using Python, PostgreSQL, dbt, Airflow, and Streamlit.

## Project Goal

The goal of this project is to build a recurring batch data pipeline that collects job postings from an external API, stores raw data in PostgreSQL, models the data with dbt, applies data quality checks, and presents market insights through a dashboard and weekly reports.

The first MVP focuses on Germany and a small set of data-focused roles:

- Data Engineer
- Analytics Engineer
- AI Engineer

## Why Germany First?

Germany is the initial focus because it keeps the project scope manageable while staying close to the target job market. Starting with one country makes it easier to validate the ingestion logic, database design, dbt models, and dashboard before expanding to other markets.

## Why PostgreSQL?

PostgreSQL is used as the main database because it supports practical data engineering patterns such as raw data storage, JSONB columns, upserts, indexing, backups, and exports. It also keeps the project local, reproducible, and sustainable without relying on cloud trials or billing.

## Planned Pipeline Flow

Adzuna API  
-> Python ingestion  
-> Local JSONL raw archive  
-> PostgreSQL raw schema  
-> dbt staging, intermediate, and mart models  
-> data quality and freshness checks  
-> Airflow orchestration  
-> Streamlit dashboard  
-> weekly Markdown report

## MVP Scope

The first successful MVP will:

- collect 100-300 real job postings for Germany
- cover Data Engineer, Analytics Engineer, and AI Engineer roles
- save raw API responses as local JSONL files
- load normalized records into PostgreSQL
- prevent duplicates with an upsert strategy
- report how many records were fetched, inserted, updated, or skipped

## Project Status

Current stage: repository and environment setup.