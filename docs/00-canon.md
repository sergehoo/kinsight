# Canon d'architecture — k-insight

> **k-insight** : plateforme de gouvernance et d'intelligence décisionnelle du Groupe.
> Centre de pilotage unique consolidant données financières, RH, opérationnelles,
> commerciales, logistiques, flotte, sécurité et immobilières de toutes les filiales.

Ce document est le **canon** : il fixe les principes non négociables. Les décisions
qui tranchent un point précis vivent dans les **ADR** (`adr/`) qui **font foi** en cas
de divergence avec les sections détaillées. Convention héritée d'AUGUSTINE.

## 1. Vision

Pas un énième outil de reporting : un **système d'aide à la décision** pour dirigeants,
CA, CODIR, DAF, DRH, directeurs opérationnels. Il consolide, alerte, prévoit et
recommande — toujours **à partir des données réelles** du Data Warehouse.

## 2. Principes architecturaux (non négociables)

1. **Séparation EL / T / Service.** Airbyte fait l'_Extract-Load_ (brut, sans
   transformation). Les transformations vivent dans le Data Warehouse (SQL/dbt).
   Le backend Django _sert_ la donnée déjà modélisée — il ne transforme pas. (ADR-0003)
2. **Le backend ne touche jamais les applications métiers.** Aucune connexion directe à
   Odoo, K-Shield, K-Express, MyKaydan. La seule source du backend est le **mart** de
   l'EDW, en lecture seule. (ADR-0004)
3. **Le Data Warehouse est multi-couches** : `raw → staging → warehouse → mart`, plus
   `analytics` (résultats IA/prévisions) et `audit` (journalisation). Modélisation
   dimensionnelle (Kimball, étoile) en `warehouse`/`mart`. (ADR-0002)
4. **La sémantique des KPI fait foi dans le domaine pur Python**, testé sans base.
   Le SQL/dbt _matérialise_ ; les deux doivent rester cohérents. (ADR-0006)
5. **Multi-filiales / multi-entités de bout en bout.** Chaque fait porte sa filiale ;
   le RBAC et le masquage filtrent par périmètre autorisé. (ADR-0005)
6. **L'IA est strictement ancrée.** Elle ne raisonne que sur des métriques déclarées au
   catalogue sémantique et des chiffres issus du mart. Jamais d'invention. (ADR-0007)
7. **Conventions techniques** : PK UUID v7, montants `BIGINT` entiers (XOF, 0 décimale),
   horodatage UTC, audit trail systématique. (ADR-0008)

## 3. Chaîne de données

```
Sources (Odoo, K-Shield, K-Express, MyKaydan, Sentinel, Artemis, Excel/CSV/Sheets, APIs)
   │  Airbyte (EL — connecteurs, incrémental, CDC quand possible)
   ▼
raw         copie fidèle des sources, horodatée, jamais modifiée
   │  dbt (staging : nettoyage, typage, renommage, dédoublonnage)
   ▼
staging     données propres, 1 modèle par flux source
   │  dbt (warehouse : conformité, dimensions/faits partagés, clés de substitution)
   ▼
warehouse   dimensions & faits conformes (Kimball) — réutilisables entre marts
   │  dbt (mart : agrégats orientés métier/usage)
   ▼
mart        HR_MART, FINANCE_MART, … EXECUTIVE_MART (vues/tables servies à l'API)
   ▼
Backend Django Governance (DRF) — lecture seule sur `mart`, RBAC, audit
   ▼
Frontend BI React + Moteur IA décisionnel (ancré sur le catalogue sémantique)
```

## 4. Composants

| Couche | Stack | Rôle |
|---|---|---|
| Ingestion | Airbyte | EL des sources vers `raw` |
| EDW | PostgreSQL (schémas multiples) | stockage + transformations dbt |
| Transformation | dbt-core | `staging → warehouse → mart` |
| Backend | Django + DRF, Celery/Beat, Redis, JWT | API governance, alertes, rapports, orchestration |
| Domaine | Python pur (`backend/src/k_insight/`) | sémantique des KPI, testée |
| Frontend | React + TS + Vite + Tailwind + shadcn + TanStack Query + Zustand + ECharts | BI premium |
| IA | RAG + text-to-SQL borné sur la couche sémantique | copilote décisionnel |
| Observabilité | Prometheus, Grafana, Loki | métriques, dashboards, logs |
| Stockage objet | MinIO | exports PDF/Excel, snapshots |
| Déploiement | Docker, Dokploy, Traefik | prod |

## 5. Modules backend

`accounts` · `organizations` (filiales/entités) · `governance` (catalogue KPI, requêtes mart)
· `executive` (dashboards consolidés) · `analytics` (prévisions, anomalies) · `alerts`
· `reports` (PDF/Excel, programmés) · `audit` · `integrations` (métadonnées Airbyte/dbt)
· `ai_governance` (copilote ancré).

## 6. Data Marts cibles

`HR_MART` · `FINANCE_MART` · `ACCOUNTING_MART` · `PAYROLL_MART` · `PROCUREMENT_MART` ·
`SALES_MART` · `CRM_MART` · `PROJECT_MART` · `FLEET_MART` · `SECURITY_MART` ·
`CONSTRUCTION_MART` · `ASSET_MART` · `EXECUTIVE_MART`.

## 7. État d'avancement

Voir [`../../STATUS.md`](../../STATUS.md). Incrément en cours : **RH** (vertical complet
Airbyte → mart → API → dashboard). Cœur sémantique RH déjà implémenté et testé
(`backend/src/k_insight/kpi/hr.py`, 22 tests verts).
