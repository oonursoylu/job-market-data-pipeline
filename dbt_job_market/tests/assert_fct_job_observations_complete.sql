-- Every staged observation must reach the fact table; the joins must not drop rows.
select
    staged.row_count as staged_rows,
    fact.row_count as fact_rows

from (
    select count(*) as row_count
    from {{ ref('stg_job_posting_observations') }}
) as staged

cross join (
    select count(*) as row_count
    from {{ ref('fct_job_observations') }}
) as fact

where staged.row_count <> fact.row_count
