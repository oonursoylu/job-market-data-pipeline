select
    *
from {{ ref('fct_skill_demand_daily') }}
where deduped_posting_group_count > posting_count