{{ config(materialized='table') }}

-- Display labels live here, so every consumer shows the same skill names.
with skills as (

    select
        skill,
        category,
        pattern

    from {{ ref('skill_dictionary') }}

)

select
    skill,
    case skill
        when 'sql' then 'SQL'
        when 'aws' then 'AWS'
        when 'gcp' then 'GCP'
        when 'dbt' then 'dbt'
        when 'power bi' then 'Power BI'
        when 'dax' then 'DAX'
        when 'postgresql' then 'PostgreSQL'
        when 'mysql' then 'MySQL'
        when 'mongodb' then 'MongoDB'
        when 'mlflow' then 'MLflow'
        when 'bigquery' then 'BigQuery'
        when 'tensorflow' then 'TensorFlow'
        when 'pytorch' then 'PyTorch'
        when 'sql server' then 'SQL Server'
        when 'github actions' then 'GitHub Actions'
        when 'a/b testing' then 'A/B Testing'
        when 'ci/cd' then 'CI/CD'
        when 'etl/elt' then 'ETL / ELT'
        when 'llm' then 'LLM'
        when 'numpy' then 'NumPy'
        when 'pandas' then 'pandas'
        when 'scikit-learn' then 'scikit-learn'
        else initcap(skill)
    end as skill_label,
    category,
    pattern as match_aliases

from skills
