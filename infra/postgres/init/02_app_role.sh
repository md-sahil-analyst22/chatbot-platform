#!/bin/sh
# Least-privilege runtime role.
#   saathi_owner : owns the schema, runs migrations
#   saathi_app   : what the API/worker use. NOT owner, NOBYPASSRLS -> RLS policies apply.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_pw="$APP_DB_PASSWORD" <<'EOSQL'
CREATE ROLE saathi_app LOGIN PASSWORD :'app_pw'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT ON DATABASE saathi TO saathi_app;
GRANT USAGE ON SCHEMA public TO saathi_app;
ALTER DEFAULT PRIVILEGES FOR ROLE saathi_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO saathi_app;
ALTER DEFAULT PRIVILEGES FOR ROLE saathi_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO saathi_app;
EOSQL
