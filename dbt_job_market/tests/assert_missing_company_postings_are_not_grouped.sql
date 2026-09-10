select
    posting_group_id
from {{ ref('int_job_posting_groups') }}
where company_name_was_missing
group by posting_group_id
having count(*) > 1
