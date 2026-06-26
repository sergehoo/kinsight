# STATUS — k-insight

Dernière mise à jour : 2026-06-24 (itération 4 : flux complet live sur Postgres réel, zéro mock)

## Légende
✅ fait & vérifié · 🟡 en cours · ⬜ à faire · ⚠️ écrit mais non exécuté ici (besoin d'infra)

## Fondation (transverse)

- ✅ Décisions de cadrage (projet autonome, nom `k-insight`, 1er incrément RH)
- ✅ Canon d'architecture + 8 ADR normatifs (`docs/architecture/`)
- ✅ Arborescence du dépôt (warehouse / backend / frontend / infra)
- ✅ Domaine pur Python : `kpi/core.py`, `semantic/registry.py` (catalogue)
- ✅ DDL EDW : schémas, rôles/sécurité (`warehouse/ddl/00,01`) — **exécuté sur Postgres 16 réel**
      (rôle `k_insight_app` lit `mart`, refusé sur `warehouse` — vérifié)
- ✅ Projet Django (config + celery) + apps `accounts`, `organizations`, `governance`, `audit`
- ✅ RBAC multi-filiales : `User.scope()` → filtrage périmètre (domaine pur), masquage nominatif (hook)
- ✅ Audit trail des consultations (`audit.AccessLog`) + journalisation sur chaque requête KPI
- ✅ Auth JWT (simplejwt) câblée (`/api/v1/auth/token/`)
- ✅ Frontend React (Vite + TS + Tailwind v4 + ECharts + TanStack Query + Zustand + Framer Motion)
      — scaffold + design system (layout premium, cartes KPI, graphes) ; `npm run build` vert
- ⬜ Infra : docker-compose complet (Postgres, Redis, Airbyte, observabilité)
- ⬜ CI (lint + tests domaine + dbt build + migrations)

## Incrément 1 — RH (vertical Airbyte → mart → API → dashboard)

- ✅ Sémantique RH : 6 métriques au catalogue (`semantic/hr.py`)
- ✅ Calculs RH purs + tests : effectif, entrées/sorties, turnover, absentéisme, masse salariale
      → **22 tests verts** (`backend/tests/test_hr_kpis.py`)
- ✅ Modèle en étoile HR_MART (`warehouse/ddl/marts/hr_mart.sql`) — **exécuté & validé sur Postgres 16**
- ✅ Seed de démo (`warehouse/ddl/seeds/hr_demo_seed.sql`) → `mart.hr_kpi` renvoie les chiffres vérifiés
      (3 110 000 / KRE 2 150 000 / KSH 960 000 ; entrées 1 ; sorties 2)
- ⚠️ Modèles dbt RH (`stg_odoo__employees`, `stg_odoo__payslips`, `mart hr_kpi`) — à `dbt build`
      (la vue mart est validée ; reste à reproduire la chaîne via dbt sur du `raw` Airbyte)
- ⬜ Connecteur Airbyte Odoo RH → `raw.odoo_hr_employee` / `raw.odoo_hr_payslip`
- ✅ API governance : `GET /api/v1/governance/catalog/` + `GET /api/v1/governance/hr/kpi/`
      (lecture mart via passerelle, filtré par périmètre) — **6 tests d'API verts**
- ✅ Réconciliation **domaine pur ↔ grain du mart** (Python, miroir du SQL) — verte
- ✅ Réconciliation domaine ↔ **SQL réel** (vue `mart.hr_kpi` sur Postgres) — chiffres identiques aux tests
- 🟡 Réconciliation domaine ↔ **dbt** : reste à reproduire la chaîne via `dbt build` (vue DDL déjà validée)
- 🟡 Turnover via API : nécessite un fait `headcount` (instantané) au mart ; en attendant, variation
      nette entrées − sorties exposée
- ✅ Dashboard RH React : masse salariale, entrées/sorties, variation nette, masse par filiale (ECharts),
      répartition, filtres globaux année/trimestre (Zustand). Rendu vérifié (capture, console sans erreur).
- ✅ Branchement front ↔ API réelle : **prouvé en local** (React → API HTTP+JWT → Django → Postgres),
      dashboard affichant les vraies données du mart (capture). Mock désactivable via `VITE_USE_MOCK=false`.
- ⬜ Drill-through par département, export PDF/Excel, dashboard exécutif consolidé

### Comment vérifier
- Backend : `cd backend && bash scripts/verify.sh` → 29 tests domaine + 6 tests API Django.
- Frontend : `cd frontend/web && npm install && npm run build` (typecheck + build) ; `npm run dev` pour le rendu.
- **Bout en bout (Postgres réel)** : voir [`docs/DEMARRAGE_LOCAL.md`](docs/DEMARRAGE_LOCAL.md).

## Prochains incréments (ordre indicatif)

1. **Finance + Exécutif** (trésorerie, cashflow, rentabilité, dashboard consolidé groupe)
2. **Flotte K-Express** (coûts véhicules, carburant, km, maintenance)
3. **Sécurité K-Shield** (pointages RFID, présence sites, incidents)
4. **Commercial / CRM**, **Logistique**, **Comptable**, **Immobilier**
5. **IA décisionnelle** : copilote ancré (text-to-SQL borné), prévisions, détection d'anomalies
6. **Alertes** + **Rapports programmés** (PDF/Excel) + **observabilité**

## Décisions ouvertes (à trancher avec le métier / en ADR)
- Auth/SSO groupe (Keycloak vs Django+JWT).
- Multidevise si filiale hors zone XOF.
- Marts : tables matérialisées vs vues, fréquence de rafraîchissement.
- Modèles de prévision par domaine.
