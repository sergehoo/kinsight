# ADR-0004 — Le backend lit le `mart` en lecture seule, jamais les sources

- **Statut** : Accepté (2026-06-23)
- **Contexte** : Principe directeur du brief : « le backend ne doit jamais interroger
  directement les applications métiers ; toutes les données proviennent du Data Warehouse ».

## Décision

- Le backend Django se connecte au PostgreSQL de l'EDW via un **rôle en lecture seule**
  (`k_insight_app`) qui n'a `SELECT` **que** sur les schémas `mart` et `analytics`
  (et `INSERT` sur `audit`). Aucun `SELECT` sur `raw`/`staging`/`warehouse`.
- Les tables applicatives propres à Django (utilisateurs, rôles, config, abonnements aux
  rapports) vivent dans une **base/schéma applicatif distinct** (`app`), jamais mélangées
  aux données analytiques.
- Aucun connecteur Django vers Odoo/K-Shield/K-Express/MyKaydan. Ces intégrations passent
  exclusivement par Airbyte.

## Conséquences

- Surface d'attaque réduite ; impossible de corrompre la donnée analytique depuis l'app.
- Les permissions PostgreSQL deviennent une seconde barrière après le RBAC applicatif.
- DDL des rôles : `warehouse/ddl/01_roles_security.sql`.
