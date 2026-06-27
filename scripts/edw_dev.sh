#!/bin/sh
# =============================================================================
# edw_dev.sh — EDW PostgreSQL éphémère pour le DÉVELOPPEMENT LOCAL (sans Docker).
#
# Monte une instance Postgres locale, applique les schémas + marts + seeds de
# démonstration (dont mart.hr_score), accorde la lecture seule à k_insight_app,
# puis affiche la commande pour lancer Django branché dessus.
#
# Idempotent : relançable sans risque. NE PAS utiliser en production
# (la prod passe par infra/postgres + Airbyte/dbt sur le vrai Data Warehouse).
#
# Usage :
#   sh scripts/edw_dev.sh up      # initialise / démarre / (re)seed
#   sh scripts/edw_dev.sh down     # arrête et supprime l'instance éphémère
# =============================================================================
set -eu

PGBIN="${PGBIN:-/Library/PostgreSQL/18/bin}"
PGDATA="${EDW_DEV_PGDATA:-/tmp/kedw}"
PORT="${EDW_DB_PORT:-5439}"
APP_USER="${EDW_DB_USER:-k_insight_app}"
APP_PASS="${EDW_DB_PASSWORD:-devpass}"
EDW_DB="${EDW_DB_NAME:-k_insight_edw}"

export PATH="$PGBIN:$PATH"
export LC_ALL=C LANG=C

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DDL="$ROOT/warehouse/ddl"

cmd="${1:-up}"

if [ "$cmd" = "down" ]; then
  pg_ctl -D "$PGDATA" stop -m fast >/dev/null 2>&1 || true
  rm -rf "$PGDATA"
  echo "EDW dev arrêté et supprimé ($PGDATA)."
  exit 0
fi

# --- init (si absent) ---
if [ ! -d "$PGDATA/base" ]; then
  rm -rf "$PGDATA"
  initdb -D "$PGDATA" -U postgres --auth=trust -E UTF8 --no-locale >/dev/null
  echo "initdb OK ($PGDATA)"
fi

# --- démarrage (si arrêté) ---
if ! pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" -o "-p $PORT -k $PGDATA -c listen_addresses='127.0.0.1'" -w start >/dev/null
  echo "Postgres démarré sur 127.0.0.1:$PORT"
fi

P() { psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "$PORT" -U postgres "$@"; }

# --- rôle + base (si absents) ---
P -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$APP_USER'" | grep -q 1 \
  || P -d postgres -c "CREATE ROLE $APP_USER LOGIN PASSWORD '$APP_PASS';" >/dev/null
P -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$EDW_DB'" | grep -q 1 \
  || P -d postgres -c "CREATE DATABASE $EDW_DB OWNER postgres;" >/dev/null

# --- schémas + marts + seeds (idempotents) ---
P -d "$EDW_DB" -f "$DDL/00_schemas.sql"                    >/dev/null
P -d "$EDW_DB" -f "$DDL/marts/hr_mart.sql"                 >/dev/null
P -d "$EDW_DB" -f "$DDL/marts/hr_score.sql"                >/dev/null
P -d "$EDW_DB" -f "$DDL/marts/domain_score.sql"            >/dev/null
P -d "$EDW_DB" -f "$DDL/seeds/hr_demo_seed.sql"            >/dev/null
P -d "$EDW_DB" -f "$DDL/seeds/hr_score_demo_seed.sql"      >/dev/null
P -d "$EDW_DB" -f "$DDL/seeds/domain_score_demo_seed.sql"  >/dev/null

# --- lecture seule sur le mart ---
P -d "$EDW_DB" -c "
GRANT CONNECT ON DATABASE $EDW_DB TO $APP_USER;
GRANT USAGE ON SCHEMA mart, analytics TO $APP_USER;
GRANT SELECT ON ALL TABLES IN SCHEMA mart, analytics TO $APP_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA mart, analytics GRANT SELECT ON TABLES TO $APP_USER;
" >/dev/null

ROWS=$(P -d "$EDW_DB" -tAc "SELECT count(*) FROM mart.hr_score")
DROWS=$(P -d "$EDW_DB" -tAc "SELECT count(*) FROM mart.domain_score")
echo "mart.hr_score : $ROWS lignes · mart.domain_score : $DROWS lignes (démonstration)."
echo ""
echo "Lancer Django branché sur cet EDW :"
echo "  cd backend && EDW_DB_HOST=127.0.0.1 EDW_DB_PORT=$PORT EDW_DB_NAME=$EDW_DB \\"
echo "    EDW_DB_USER=$APP_USER EDW_DB_PASSWORD=$APP_PASS python manage.py runserver"
