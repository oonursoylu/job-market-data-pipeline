-- Every segment and date in the fact table must appear once in the coverage table,
-- with the same counts, so BI tools that use the coverage table include the same dates.
with from_fact as (

    select
        segment_id,
        extract_date,
        count(distinct job_posting_key) as observed_postings,
        count(distinct posting_group_id) as observed_groups

    from {{ ref('fct_job_observations') }}

    group by segment_id, extract_date

)

select
    coalesce(from_fact.segment_id, coverage.segment_id) as segment_id,
    coalesce(from_fact.extract_date, coverage.extract_date) as extract_date

from from_fact
full outer join {{ ref('fct_segment_coverage') }} as coverage
    on from_fact.segment_id = coverage.segment_id
    and from_fact.extract_date = coverage.extract_date

where from_fact.segment_id is null
    or coverage.segment_id is null
    or from_fact.observed_postings <> coverage.observed_postings
    or from_fact.observed_groups <> coverage.observed_groups
