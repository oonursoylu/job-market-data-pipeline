select
    *
from {{ ref('mart_country_role_skill_demand') }}
where deduped_total_skill_mentions > total_skill_mentions