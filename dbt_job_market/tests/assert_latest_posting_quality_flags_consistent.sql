select
    source,
    job_id
from {{ ref('mart_latest_postings') }}
where
    coalesce(posting_age_days < 0, false)
    or is_stale_at_latest_observation is distinct from coalesce(posting_age_days > 90, false)
