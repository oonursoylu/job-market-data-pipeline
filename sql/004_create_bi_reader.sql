-- Optional: a read-only login for Power BI, limited to the dbt models in the analytics schema.
-- Run once as a superuser (it asks for the new password):
--
--   psql -h localhost -U postgres -d job_market -f .\sql\004_create_bi_reader.sql
--
-- dbt drops and recreates its tables on every build, so a plain GRANT would be lost after
-- the next build. ALTER DEFAULT PRIVILEGES grants SELECT on every table job_market_user
-- creates in analytics from now on.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_reader') THEN
        CREATE ROLE bi_reader LOGIN;
    END IF;
END
$$;

\password bi_reader

GRANT CONNECT ON DATABASE job_market TO bi_reader;
GRANT USAGE ON SCHEMA analytics TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO bi_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE job_market_user IN SCHEMA analytics
    GRANT SELECT ON TABLES TO bi_reader;
