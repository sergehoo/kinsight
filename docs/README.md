# k-insight

**Plateforme de Gouvernance et d'Intelligence Décisionnelle du Groupe.**
Centre de pilotage unique consolidant les données de toutes les filiales
(finances, RH, opérations, commercial, logistique, flotte, sécurité, immobilier)
dans une expérience BI premium, alimentée par un Data Warehouse central et un
copilote IA strictement ancré sur les données réelles.

## Architecture (résumé)

```
Sources (Odoo, K-Shield, K-Express, MyKaydan, Sentinel, Artemis, Excel/CSV/Sheets, APIs)
  → Airbyte (EL)  → PostgreSQL EDW (raw→staging→warehouse→mart + analytics + audit)
  → dbt (T)       → Backend Django Governance (lecture seule sur mart)
  → Frontend BI React  + Moteur IA décisionnel
```

Principes (détaillés dans [`docs/architecture/00-canon.md`](docs/architecture/00-canon.md)) :

1. Airbyte = EL seul ; dbt = transformations ; Django ne transforme pas.
2. Le backend ne touche jamais les sources — uniquement le `mart`, en lecture seule.
3. EDW multi-schémas, modélisation Kimball (étoile).
4. La sémantique des KPI vit dans un **domaine pur Python testé** (`backend/src/k_insight/`).
5. Multi-filiales / RBAC / masquage de bout en bout.
6. IA strictement ancrée sur le catalogue sémantique — jamais d'invention.

Décisions normatives : [`docs/architecture/README.md`](docs/architecture/README.md) (ADR 0001–0008).

## Arborescence

```
k-insight/
├── docs/architecture/      # canon + ADR (font foi)
├── warehouse/
│   ├── ddl/                # schémas, sécurité, marts (SQL de référence)
│   └── dbt/                # transformations staging → warehouse → mart
├── backend/
│   ├── src/k_insight/      # DOMAINE PUR : kpi/ (calculs) + semantic/ (catalogue)
│   └── tests/              # unittest, sans base de données
├── frontend/               # BI React (à venir)
└── infra/                  # docker-compose, observabilité
```

## Démarrage rapide (domaine pur — vérifiable sans infra)

```bash
cd backend
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

22 tests RH doivent passer (effectif, turnover, masse salariale, ancrage du catalogue).

## État

Voir [`STATUS.md`](STATUS.md). Incrément en cours : **RH**.
