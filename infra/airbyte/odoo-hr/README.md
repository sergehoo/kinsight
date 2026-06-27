# Airbyte — Source Odoo RH → schéma `raw`

Connexion **connecteur Odoo natif** (choix retenu), champs filiale/département **explicites**
(mapping 1:1 vers le contrat `raw`, cf. `warehouse/ddl/raw/00_raw_odoo_hr.sql`). Airbyte fait
l'**EL uniquement** (ADR-0003) ; la transformation est faite par dbt.

## 0. Préflight (obligatoire, avant Airbyte)
Sur votre infra (Odoo joignable), renseigner `env.odoo.example` → `.env.odoo`, injecter la clé,
puis :
```bash
set -a && . ./.env.odoo && set +a
export ODOO_API_KEY="$(votre-secret-manager get odoo_rh_api_key)"   # jamais en clair dans un fichier versionné
python3 scripts/odoo_hr_preflight.py
```
Attendu : `✓ Préflight OK — schéma compatible`. Si des champs sont **ABSENTS**, le script
propose des candidats → on ajuste le mapping (étape 2) avant de continuer.

## 1. Source (connecteur Odoo)
| Champ Airbyte | Valeur |
|---|---|
| Host / URL | `${ODOO_URL}` |
| Database | `${ODOO_DB}` |
| Username | `${ODOO_LOGIN}` |
| Password / API key | `${ODOO_API_KEY}` — **stocké chiffré par Airbyte**, jamais en clair |

## 2. Streams → tables `raw` (mapping 1:1)
Sélectionner uniquement les deux streams et les champs du contrat :

| Stream Odoo | Table destination | Champs (sélection) |
|---|---|---|
| `hr.employee` | `raw.odoo_hr_employee` | `id, name, subsidiary_code, department_code, date_hired, date_departure` |
| `hr.payslip`  | `raw.odoo_hr_payslip`  | `id, employee_id, subsidiary_code, department_code, date_from, gross_amount, net_amount, employer_charges` |

- **Sync mode** : `Incremental | Dedup`, **curseur** `write_date`, **clé primaire** `id`.
- Si un champ Odoo a un nom différent (révélé par le préflight), le renommer ici OU dans le
  staging dbt (`stg_odoo__employees.sql` / `stg_odoo__payslips.sql`) — garder le **contrat raw** stable.

## 3. Destination (Postgres → `raw`)
| Champ | Valeur |
|---|---|
| Host | `postgres` (réseau compose) ou l'hôte EDW |
| Database | EDW (`k_insight_edw`) |
| Default Schema | **`raw`** |
| User | `k_insight_airbyte` (écrit `raw` seulement — provisionné par `infra/postgres/init/`) |
| Table name override | `odoo_hr_employee` / `odoo_hr_payslip` (sans préfixe) |

## 4. Lancer + enchaîner
```bash
# 1ʳᵉ sync (UI Airbyte ou API/abctl), puis :
cd infra && docker compose --profile dbt run --rm kinsight-dbt build   # staging + mart.hr_kpi + tests
psql -d k_insight_edw -tAc "SELECT sum(payroll_mass_xof) FROM mart.hr_kpi WHERE month_start >= date_trunc('quarter', now());"
```
Le backend lit déjà `mart.hr_kpi` (lecture seule) → l'API RH, les scores et le Copilot passent
au **réel** sans changement de code. Détail complet : `docs/runbooks/01-source-odoo-rh.md`.
