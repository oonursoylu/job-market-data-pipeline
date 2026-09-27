-- The skill bridge works at group level, so every member of a posting group
-- must match exactly the same skills. Returns group and skill pairs that break this.
with group_sizes as (

    select
        posting_group_id,
        count(*) as member_count

    from {{ ref('int_job_posting_groups') }}

    group by posting_group_id

),

matching_members as (

    select
        posting_groups.posting_group_id,
        job_skills.skill,
        count(*) as matching_member_count

    from {{ ref('int_job_posting_skills') }} as job_skills
    inner join {{ ref('int_job_posting_groups') }} as posting_groups
        on job_skills.source = posting_groups.source
        and job_skills.job_id = posting_groups.job_id

    group by
        posting_groups.posting_group_id,
        job_skills.skill

)

select
    matching_members.posting_group_id,
    matching_members.skill,
    matching_members.matching_member_count,
    group_sizes.member_count

from matching_members
inner join group_sizes
    on matching_members.posting_group_id = group_sizes.posting_group_id

where matching_members.matching_member_count <> group_sizes.member_count
