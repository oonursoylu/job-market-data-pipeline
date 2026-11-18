# Power BI model

This is the plan for the Power BI report on the dbt star schema. It uses the same counting rules as the Streamlit dashboard, and `dashboard/check_bi_model.py` checks those rules in SQL against the dashboard queries.

## 1. Connect

1. Optional but recommended: create a read-only login with `sql/004_create_bi_reader.sql`.
2. In Power BI Desktop: **Get data → PostgreSQL database**. Server `localhost`, database `job_market`, mode **Import**. The data is small, and Import keeps distinct counts fast.
3. If Power BI reports that the remote certificate is invalid, the local server has no SSL. Go to **File → Options and settings → Data source settings → Edit Permissions** and clear **Encrypt connections**.
4. Import only these eight tables from the `analytics` schema. Leave out `raw`, staging and intermediate models, and do not import `raw_json`.

| Table | Grain |
|---|---|
| `fct_job_observations` | one posting seen in one country and role search on one date |
| `fct_segment_coverage` | one segment on one collected date |
| `dim_date` | one calendar day |
| `dim_segments` | one country and role pair |
| `dim_posting_groups` | one analytical group |
| `dim_job_postings` | one source posting |
| `dim_skills` | one tracked skill |
| `bridge_posting_group_skills` | one group and one skill it mentions |

## 2. Relationships

Turn off automatic relationship detection before loading, or check Model view afterwards, because Power BI would also join `dim_job_postings[posting_group_id]` to `dim_posting_groups`. That extra link creates two paths from postings to groups. Delete it if it appears.

| From (many) | To (one) | Cross-filter |
|---|---|---|
| `fct_job_observations[extract_date]` | `dim_date[date_day]` | Single |
| `fct_job_observations[segment_id]` | `dim_segments[segment_id]` | Single |
| `fct_job_observations[posting_group_id]` | `dim_posting_groups[posting_group_id]` | Single |
| `fct_job_observations[job_posting_key]` | `dim_job_postings[job_posting_key]` | Single |
| `bridge_posting_group_skills[posting_group_id]` | `dim_posting_groups[posting_group_id]` | **Both** |
| `bridge_posting_group_skills[skill]` | `dim_skills[skill]` | Single |
| `fct_segment_coverage[extract_date]` | `dim_date[date_day]` | Single |
| `fct_segment_coverage[segment_id]` | `dim_segments[segment_id]` | Single |

The one two-way relationship lets a skill filter travel dim_skills → bridge → dim_posting_groups → fct_job_observations. `fct_segment_coverage` has no path to skills, so a skill filter can never change which dates are included.

Model settings:

- Mark `dim_date` as the date table, using `date_day`.
- Sort by column: `dim_date[month_label]` by `year_month_number`, `dim_segments[segment_name]` by `segment_sort_order`, `country_name` by `country_sort_order`, `role_name` by `role_sort_order`.
- Add a report-level filter `dim_segments[is_reporting_segment] = True`.
- Hide key columns (`*_key`, `*_id`) from report view.

## 3. Measures

Put these in a separate measures table. Slicers on `dim_segments[country_name]` and `dim_segments[role_name]` select segments the same way as the dashboard sidebar.

```DAX
Source Postings =
DISTINCTCOUNT ( fct_job_observations[job_posting_key] )

Analytical Groups =
DISTINCTCOUNT ( fct_job_observations[posting_group_id] )

Fewer Entries After Grouping =
[Source Postings] - [Analytical Groups]

-- Dates on which every selected segment was collected.
Included Dates =
VAR SegmentCount = COUNTROWS ( VALUES ( dim_segments[segment_id] ) )
RETURN
    COUNTROWS (
        FILTER (
            VALUES ( dim_date[date_day] ),
            CALCULATE ( COUNTROWS ( fct_segment_coverage ) ) = SegmentCount
        )
    )

-- A group counts once per date across the selected roles, on included dates only.
Group Days =
VAR SegmentCount = COUNTROWS ( VALUES ( dim_segments[segment_id] ) )
VAR IncludedDates =
    FILTER (
        VALUES ( dim_date[date_day] ),
        CALCULATE ( COUNTROWS ( fct_segment_coverage ) ) = SegmentCount
    )
RETURN
    CALCULATE (
        DISTINCTCOUNT ( fct_job_observations[group_day_key] ),
        KEEPFILTERS ( IncludedDates )
    )

Observed Group Days =
CALCULATE ( [Group Days], REMOVEFILTERS ( dim_skills ) )

-- With a skill on rows or in a slicer: group-days that mention it. Zero instead of blank.
Group Days With Mention =
IF ( NOT ISBLANK ( [Observed Group Days] ), COALESCE ( [Group Days], 0 ) )

Skill Share =
DIVIDE ( [Group Days With Mention], [Observed Group Days] )

Average Groups Per Included Day =
DIVIDE ( [Group Days With Mention], [Included Dates] )
```

Format `Skill Share` as a percentage. A group can mention several skills, so shares across skills do not add up to 100%.

In formula form, for the selected segments S and the included dates D:

```text
included_dates  = { d : every segment in S has a row in fct_segment_coverage on d }
group_days      = COUNT DISTINCT group_day_key  WHERE segment_id IN S AND extract_date IN included_dates
skill_share     = group_days(with skill) / group_days(all skills removed)
```

## 4. Check the numbers against the dashboard

1. After `dbt build`, run `python dashboard\check_bi_model.py`. It applies the rules above in SQL and compares them with the dashboard queries for every country and role combination.
2. In Power BI, open **DAX query view** and run:

```DAX
EVALUATE
SUMMARIZECOLUMNS (
    dim_skills[skill_label],
    "Group days with mention", [Group Days With Mention],
    "Observed group days", [Observed Group Days],
    "Included dates", [Included Dates]
)
ORDER BY [Group days with mention] DESC
```

3. Compare a few scopes with the dashboard's **Skills → All tracked skills** table, using **All observed dates** and the same countries and roles. The numbers should match exactly.

## 5. Show the source

Adzuna's terms ask personal and academic users to name Adzuna as the source of the vacancy and salary data wherever it is published. Add a small text box such as "Job data: Adzuna (adzuna.co.uk)" to every page.
