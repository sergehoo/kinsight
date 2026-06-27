# Runbook 01 — Brancher la 1ʳᵉ source réelle : Odoo RH → mart

> Objectif : faire passer le domaine **RH** de « N/D gouverné » à de **vraies valeurs**, de bout
> en bout : Odoo → **Airbyte (EL)** → `raw.odoo_hr_*` → **dbt** → `mart.hr_kpi` → API Django →
> Frontend + Copilot. Tout le logiciel est prêt ; ce runbook est exécutable dès que les
> **accès §0** sont disponibles. Une **répétition locale sans Odoo** est fournie (§6) — déjà
> vérifiée (3 110 000 XOF / 1 entrée / 2 sorties).

## 0. Prérequis (§0 — bloquants d'accès)
- Credentials **Odoo** (URL, base, user API en lecture).
- **EDW PostgreSQL persistant** (volume) — pas l'instance éphémère de dev.
- Rôles provisionnés par `infra/postgres/init/` : `k_insight_airbyte` (écrit `raw` seulement),
  `k_insight_dbt` (transforme), `k_insight_app` (lecture `mart` seule).

## 1. Démarrer l'infra persistante
```bash
cd infra
# Prod : ne PAS semer les démos
SEED_DEMO_DATA=false docker compose -f docker-compose.yml up -d kinsight-postgres kinsight-redis kinsight-minio kinsight-backend
```
Le DDL EDW (schémas + `mart.hr_kpi`) est appliqué au 1ᵉʳ démarrage (cf. `infra/postgres/init/`).

## 2. Déclarer la source dans le control-plane
Dans l'app (`/admin/integrations` → Nouvelle source) ou via l'API `integrations` :
créer une `IntegrationSource` « Odoo RH » (secrets chiffrés au repos, jamais affichés —
ADR-0009). Sert au suivi/santé/déclenchement ; le flux de données passe par Airbyte (le
frontend n'appelle jamais Odoo directement).

## 2bis. Préflight Odoo (dé-risque tout)
Avant Airbyte, valider auth + schéma depuis votre infra (clé via secret, jamais en clair) :
```bash
cp infra/airbyte/odoo-hr/env.odoo.example .env.odoo   # renseigner URL/DB/LOGIN
set -a && . ./.env.odoo && set +a
export ODOO_API_KEY="$(votre-secret-manager get odoo_rh_api_key)"
python3 scripts/odoo_hr_preflight.py        # attendu : ✓ Préflight OK
```
S'il signale des champs ABSENTS, ajuster le mapping (étape 3) avant de continuer.

## 3. Configurer Airbyte (connecteur Odoo natif → schéma `raw`)
Spec détaillée : **`infra/airbyte/odoo-hr/README.md`**. En résumé :
- **Source** : connecteur Odoo (`${ODOO_URL}`, `${ODOO_DB}`, `${ODOO_LOGIN}`, clé chiffrée par Airbyte).
- **Destination** : Postgres → host `postgres`, base EDW, **schéma `raw`**, rôle `k_insight_airbyte`.
- **Streams → tables** (contrat = `warehouse/ddl/raw/00_raw_odoo_hr.sql`, mapping 1:1) :
  - `hr.employee` → `raw.odoo_hr_employee` (`id, name, subsidiary_code, department_code, date_hired, date_departure`)
  - `hr.payslip`  → `raw.odoo_hr_payslip`  (`id, employee_id, subsidiary_code, department_code, date_from, gross_amount, net_amount, employer_charges`)
- Mode **Incremental | Dedup**, curseur `write_date`, clé `id` ; planifié (Celery Beat trace dans `audit`).

## 4. Première synchronisation
Lancer la sync (UI Airbyte ou `abctl`/API). Vérifier le remplissage :
```sql
SELECT count(*) FROM raw.odoo_hr_employee;
SELECT count(*) FROM raw.odoo_hr_payslip;
```

## 5. Transformer (dbt) puis tester
```bash
cd infra && docker compose --profile dbt run --rm kinsight-dbt build
```
`dbt build` matérialise `staging.stg_odoo__*` (vues) puis **`mart.hr_kpi`** (table), et exécute
les tests — dont la **réconciliation** `tests/assert_hr_kpi_reconciliation.sql` (masse salariale
mart = somme des bulletins ; entrées = nb employés ; sorties = nb départs).

## 6. Répétition LOCALE sans Odoo (déjà vérifiée)
Pour valider la chaîne raw→mart sans credentials (utile en CI/dev) :
```bash
psql -d <edw> -c "CREATE SCHEMA IF NOT EXISTS raw; CREATE SCHEMA IF NOT EXISTS staging;"
psql -d <edw> -f warehouse/ddl/raw/00_raw_odoo_hr.sql
psql -d <edw> -f warehouse/ddl/seeds/raw_odoo_hr_demo_seed.sql      # raw Airbyte-shaped
psql -d <edw> -f warehouse/ddl/transform/odoo_hr_compiled.sql      # = modèles dbt compilés
psql -d <edw> -tAc "SELECT sum(payroll_mass_xof) FROM mart.hr_kpi
                    WHERE month_start BETWEEN '2026-01-01' AND '2026-03-01';"
# Attendu : 3110000  (entrées Q1 = 1, sorties Q1 = 2)
```

## 7. Exposer le réel (aucun changement de code)
Le backend lit déjà `mart.hr_kpi` en lecture seule via `PostgresMartGateway` (ADR-0004).
Pointer `EDW_DB_*` sur l'EDW persistant suffit : `GET /api/v1/governance/hr/kpi/`, le module RH,
les scores RH et le **Copilot** (`hr.payroll_mass`, etc.) renvoient alors les **vraies valeurs**
au lieu de N/D — sans modification applicative.

## 8. Vérifier dans l'application
- API : `GET /api/v1/governance/hr/kpi/?year=&quarter=` → valeurs réelles.
- Copilot : « masse salariale du trimestre » → valeur réelle sourcée `mart.hr_kpi`.
- Module RH : KPI + Human Capital Score alimentés.

## Domaines suivants
Répéter ce schéma par domaine (ordre proposé : RH ✅ → Finance → Immobilier → Opérations →
Commercial → Risques) : contrat `raw`, streams Airbyte, modèles dbt (`stg_*` + `mart.<domaine>_kpi`),
test de réconciliation, puis branchement des **bindings métrique→mart** (`value_resolver.py` +
`bindings.py`) pour que catalogue/IA/vues servent le réel.
```
