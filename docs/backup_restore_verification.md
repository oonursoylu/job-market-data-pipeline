# PostgreSQL backup and restore verification

## Result

**Passed on 2026-09-07 (Europe/Berlin).** A custom-format backup was restored into a separate, empty test database on PostgreSQL 18.4. All 11 tables matched the source, including every row and its duplicate count.

The backup was created on 2026-09-06 at 23:56:52 local time. It contains database objects and data; it does not include server roles, passwords, PostgreSQL configuration, Python code or external JSONL archives.

## Procedure used

Commands were run from the repository root in Windows PowerShell. Passwords were entered at the prompt and are not included here.

### 1. Create the backup

```powershell
$backupPath = ".\backups\job_market_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"
pg_dump -h localhost -p 5432 -U job_market_user -d job_market -Fc -f $backupPath
if ($LASTEXITCODE -ne 0) { throw "Backup failed. Stop here." }
```

### 2. Read the archive contents

```powershell
pg_restore --list $backupPath
if ($LASTEXITCODE -ne 0) { throw "Archive check failed. Stop here." }
```

The contents list was readable and included tables, table data, views, sequences, constraints and indexes. This check alone does not prove a successful restore.

### 3. Restore to a separate database

A database administrator created an empty database named `job_market_restore_check_20260907`, owned by `job_market_user`. The project account does not have permission to create databases.

With that empty target created, the restore command was:

```powershell
pg_restore -h localhost -p 5432 -U job_market_user -d job_market_restore_check_20260907 --single-transaction --exit-on-error --verbose $backupPath
if ($LASTEXITCODE -ne 0) { throw "Restore failed. Stop here." }
```

The restore completed without errors. The original `job_market` database was not the restore target. The test database was retained after verification.

### 4. Compare data and structure

Both databases were read in repeatable-read, read-only transactions with UTC session time zones. Table rows were serialised with PostgreSQL `row_to_json` and compared as multisets: row order does not matter, but duplicate counts do. No source data or credentials are included in this report.

| Table | Source rows | Restored rows | Content match |
|---|---:|---:|---|
| `analytics.fct_role_demand_daily` | 111 | 111 | Pass |
| `analytics.fct_skill_demand_daily` | 1,732 | 1,732 | Pass |
| `analytics.int_job_posting_groups` | 5,006 | 5,006 | Pass |
| `analytics.int_job_posting_skills` | 2,051 | 2,051 | Pass |
| `analytics.mart_country_role_demand` | 6 | 6 | Pass |
| `analytics.mart_country_role_skill_demand` | 165 | 165 | Pass |
| `analytics.mart_latest_postings` | 5,002 | 5,002 | Pass |
| `analytics.mart_skill_demand_dashboard` | 165 | 165 | Pass |
| `analytics.skill_dictionary` | 53 | 53 | Pass |
| `raw.job_posting_observations` | 16,493 | 16,493 | Pass |
| `raw.job_postings` | 5,006 | 5,006 | Pass |

The following also matched:

- Schema names, owners and schema permissions
- Table, view and sequence inventory
- Column definitions, order, defaults and nullability
- Constraint definitions and validation state
- Index definitions and view definitions
- Object owners and access permissions
- Sequence settings, current values and `is_called` state

## Archive identity

- File: `job_market_20260906_235652.dump`
- Size: 2,814,616 bytes
- SHA-256: `2c141b15868b53622b5185494b39236cfe26fb1249d54276670ab33263900f05`

## Scope of verification

The restored data matched the source database at verification time. A separate reference snapshot was not captured when the dump was created, so this is not an independent comparison against a recorded dump-time baseline.

This test covers recovery on the same server with the existing role. It does not verify recovery on another computer or server. The archive is excluded from Git by the `backups/*` rule. No off-device copy was verified as part of this test.
