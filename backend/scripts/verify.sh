#!/usr/bin/env bash
# Vérification k-insight.
#  [1] domaine pur (KPI, accès, réconciliation) — sans dépendance, tourne partout.
#  [2] couche Django (check + migrations + tests d'API) — nécessite les deps backend.
#  À venir : dbt build + dbt test sur l'EDW PostgreSQL.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> [1/2] Tests du domaine pur (sans base de données)"
PYTHONPATH=src python3 -m unittest discover -s tests

echo
echo "==> [2/2] Couche Django (check + tests d'API, base SQLite éphémère)"
python3 manage.py check
python3 manage.py test apps

echo
echo "OK — domaine pur + API Django vérifiés."
echo "À venir (nécessite Postgres) : dbt build/test + réconciliation domaine <-> mart dbt."
