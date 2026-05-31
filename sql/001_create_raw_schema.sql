CREATE SCHEMA IF NOT EXISTS raw;

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS raw.job_postings (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    job_id TEXT NOT NULL,
    job_title TEXT,
    company_name TEXT,
    location TEXT,
    country TEXT,
    description TEXT,
    salary_min NUMERIC(12, 2),
    salary_max NUMERIC(12, 2),
    currency TEXT,
    contract_type TEXT,
    category TEXT,
    redirect_url TEXT,
    created_at TIMESTAMPTZ,
    search_role TEXT NOT NULL,
    search_country TEXT NOT NULL,
    raw_json JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    extract_date DATE NOT NULL,
    CONSTRAINT uq_job_postings_source_job_id UNIQUE (source, job_id),
    CONSTRAINT chk_job_postings_salary_range CHECK (
        salary_min IS NULL
        OR salary_max IS NULL
        OR salary_min <= salary_max
    )
);

CREATE INDEX IF NOT EXISTS idx_job_postings_extract_date
ON raw.job_postings (extract_date);

CREATE INDEX IF NOT EXISTS idx_job_postings_search_country_role
ON raw.job_postings (search_country, search_role);

CREATE INDEX IF NOT EXISTS idx_job_postings_created_at
ON raw.job_postings (created_at);

CREATE INDEX IF NOT EXISTS idx_job_postings_loaded_at
ON raw.job_postings (loaded_at);