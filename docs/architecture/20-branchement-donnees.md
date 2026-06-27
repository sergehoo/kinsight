# Branchement des données réelles — backlog

> État : le **frontend** est complet (9 domaines, ~97 vues, accueils hero) mais affiche du **N/D gouverné**.
> Seul le **RH** est câblé bout-en-bout (sur EDW de démo). API réelle = `catalog/` (RH), `overview/`, `hr/kpi/`.

Légende : ✅ fait · 🟡 partiel · ⬜ à faire · ⛔ bloqué (décision/accès requis)

## 0. Décisions / accès (bloquants)
- ⛔ Credentials sources : Odoo, K-Shield, K-Express, MyKaydan, CRM, Google Sheets (lecture).
- ⛔ Hébergement EDW **persistant** (l'instance actuelle est éphémère).
- ⬜ Ordre d'industrialisation : RH → Finance → Immobilier → Opérations → Commercial → Risques.

## 1. Socle (infra persistante)
- ⬜ `docker-compose` complet persistant : PostgreSQL EDW (volume), Redis, MinIO, Airbyte, runner dbt, Django + Celery/Beat.
- 🟡 DDL schémas/sécurité/mart HR (exécutés sur instance éphémère ; à rejouer sur instance pérenne).

## 2. Ingestion — Airbyte (EL)
- ⬜ Connecteur Odoo → `raw.odoo_*` (RH, compta, ventes, achats, stocks, projets).
- ⬜ Connecteurs K-Shield, K-Express, MyKaydan, CRM, CSV/Sheets → `raw.*`.
- ⬜ Incrémental + CDC, planifiés (Celery Beat), runs tracés dans `audit`.

## 3. Transformation — dbt
- ✅ Modèles RH (`stg_odoo__employees/payslips`, `mart hr_kpi`).
- ⬜ Dimensions conformes (`dim_date/subsidiary/employee/department/project`).
- ⬜ 13 marts restants (FINANCE, REAL_ESTATE, OPS, SALES/CRM, SECURITY, RISK, ASSET, EXECUTIVE…).
- ⬜ Tests dbt + docs + réconciliation domaine pur ↔ dbt.

## 4. Couche sémantique (domaine pur + catalogue)
- ✅ RH : 6 métriques + calculs testés.
- ⬜ Étendre catalogue + KPI purs aux autres domaines (sinon `catalog/` et l'IA restent RH-only).

## 5. API backend governance
- ✅ Endpoints catalog/overview/hr-kpi + `PostgresMartGateway`.
- ✅ **Endpoint générique** `GET /governance/module/:key/` + registre `MART_BINDINGS` (`bindings.py`) :
      clé liée → valeurs réelles + séries depuis le mart ; clé non liée → `available:false` (gouverné).
      RBAC périmètre + audit appliqués. **Vérifié en HTTP réel** (hr-executive → 3 110 000 XOF ; com-crm → gouverné).
- 🟡 Bindings : seul le RH (`hr-executive`, `hr-payroll`) est lié — étendre mart par mart.
- ⬜ Cache Redis ; pagination ; masquage colonnes sensibles.

## 6. Frontend — câblage réel
- ✅ Hook générique `useModuleData(key, year, quarter)` + injection des **valeurs réelles** dans `ModulePage`
      (KPI lié → vraie valeur formatée + tag « Donnée EDW » ; non lié → N/D). **Vérifié DOM** : RH exécutif affiche
      Masse salariale 3 110 000 F CFA, Recrutements 1, Départs 2.
- ✅ Séparation **dev = mock** (`.env.development`) / **build prod = API réelle** (`.env.local`, non commité).
- ⬜ Login JWT réel (token en dur pour la démo) ; filtres globaux → query params déjà transmis (year/quarter) ;
      états loading/empty/error ; valeurs réelles dans les accueils hero ; séries ECharts depuis `series`.

## 7. Sécurité / RBAC bout-en-bout
- ✅ Rôles + `scope()` + filtrage (vérifié RH).
- ⬜ Login réel (permissions servies par le backend) ; RLS PostgreSQL ; masquage colonnes sensibles.

## 8. IA décisionnelle
- ⬜ text-to-SQL borné sur mart/analytics + ancrage catalogue ; endpoint `ai/query` journalisé ; vues IA/CODIR.

## 9. Alertes
- ⬜ Règles Celery Beat sur marts → `analytics.alerts` → endpoint → Centre d'alertes / « Signaux & seuils ».

## 10. Rapports
- ⬜ Export PDF/Excel (MinIO), rapports programmés (DG/CODIR/DAF) + endpoint + UI.

## 11. Observabilité & CI/CD
- ⬜ Prometheus/Grafana/Loki ; CI (tests domaine + dbt build/test + migrations) ; déploiement Dokploy/Traefik.

## Séquencement recommandé
1. Socle persistant + Airbyte Odoo RH → **RH 100 % réel** = gabarit.
2. Généraliser API (§5) + hook front (§6) → dérouler domaine par domaine.
3. Transverses : Alertes, IA, Rapports, Observabilité.
