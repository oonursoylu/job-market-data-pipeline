# dbt project

These are the dbt models for the job market pipeline. The main [README](../README.md) explains the project, the counting rules and how to run everything.

## Layers

| Folder | What it holds |
|---|---|
| `models/staging` | Views that clean the raw Adzuna postings and observations. The raw values stay unchanged in PostgreSQL. |
| `models/intermediate` | Tables for analytical posting groups and skill matches, so later models do not repeat the text work. |
| `models/marts/star` | The star schema that the dashboard reads: `fct_job_observations`, `dim_job_postings`, `dim_posting_groups`, `dim_segments`, `dim_skills` and `bridge_posting_group_skills`. |
| `models/marts` | `mart_latest_postings`: one row per advert, with its latest search context and its first and latest observation dates. |
| `seeds` | The skill dictionary. |
| `tests` | Singular tests for rules that generic tests cannot express, such as postings in one group matching the same skills. |

The counting rules for reports are described on `fct_job_observations` in `models/marts/star/star_schema.yml`.

## Run

From the repository root, with a dbt profile named `dbt_job_market` that targets the PostgreSQL `analytics` schema:

```powershell
dbt build --project-dir .\dbt_job_market
dbt docs generate --project-dir .\dbt_job_market
```
