# Démarrage local — flux complet RH (vérifié)

Reproduit le flux bout en bout **sans mock** : Postgres EDW → vue `mart.hr_kpi` →
Django (rôle lecture seule) → API HTTP+JWT → dashboard React.

## 1. Une instance PostgreSQL pour l'EDW

### Option A — Docker (recommandé)

```bash
cd infra
docker compose up -d postgres        # Postgres 16, port 5432
```

Crée ensuite la base `k_insight_edw` si besoin (`createdb`), puis va en §2.

### Option B — cluster éphémère local (ce qui a été utilisé pour la démo)

Utile si le cluster Postgres existant exige un mot de passe. Cluster jetable, isolé
dans `/tmp`, port 55432, auth `trust` :

```bash
export PGDATA=/tmp/k_insight_pg LC_ALL=C        # LC_ALL=C requis sur macOS (sinon : postmaster multithreaded)
initdb -D "$PGDATA" -U postgres --auth=trust --encoding=UTF8 --locale=C
pg_ctl -D "$PGDATA" -o "-p 55432 -k /tmp -c listen_addresses=127.0.0.1" -l /tmp/k_insight_pg.log -w start
createdb -h 127.0.0.1 -p 55432 -U postgres k_insight_edw
```

> ⚠️ Éphémère : disparaît au nettoyage de `/tmp` / redémarrage. Arrêt : `pg_ctl -D /tmp/k_insight_pg stop`.

## 2. DDL + seed de démonstration

```bash
export PGHOST=127.0.0.1 PGPORT=55432 PGUSER=postgres PGDATABASE=k_insight_edw LC_ALL=C
psql -v ON_ERROR_STOP=1 -f warehouse/ddl/00_schemas.sql
psql -v ON_ERROR_STOP=1 -f warehouse/ddl/01_roles_security.sql
psql -v ON_ERROR_STOP=1 -f warehouse/ddl/marts/hr_mart.sql
psql -v ON_ERROR_STOP=1 -f warehouse/ddl/seeds/hr_demo_seed.sql
# Contrôle : doit valoir 3 110 000 (KRE 2 150 000, KSH 960 000) pour Q1 2026
psql -c "SELECT sum(payroll_mass_xof) FROM mart.hr_kpi WHERE month_start >= '2026-01-01' AND month_start < '2026-04-01';"
```

## 3. Backend Django branché sur l'EDW

```bash
cd backend
export EDW_DB_HOST=127.0.0.1 EDW_DB_PORT=55432 EDW_DB_NAME=k_insight_edw \
       EDW_DB_USER=k_insight_app EDW_DB_PASSWORD=trust LC_ALL=C
python3 manage.py migrate                         # base applicative (SQLite par défaut)
# Créer un utilisateur « groupe » :
python3 manage.py shell --no-imports -c "
from django.contrib.auth import get_user_model
get_user_model().objects.create_user('dg', password='x', role='DG_GROUP', is_group_scope=True)"
python3 manage.py runserver 127.0.0.1:8000
```

Jeton JWT pour le front :

```bash
python3 manage.py shell --no-imports -c "
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
print(str(RefreshToken.for_user(get_user_model().objects.get(username='dg')).access_token))"
```

## 4. Frontend sur l'API réelle

Créer `frontend/web/.env.development.local` (priorité max en dev ; gitignoré) :

```
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_API_TOKEN=<le jeton de l'étape 3>
```

```bash
cd frontend/web && npm install && npm run dev      # http://localhost:5173
```

Le dashboard RH affiche alors les vraies données du mart. Sans backend, repasser
`VITE_USE_MOCK=true` (ou supprimer le fichier) pour la démo hors-ligne.
