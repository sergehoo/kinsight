# ADR-0006 — La sémantique des KPI vit dans un domaine pur Python testé

- **Statut** : Accepté (2026-06-23)
- **Contexte** : Les KPI (turnover, masse salariale, rentabilité, taux d'occupation…)
  portent des règles métier subtiles (bornes de période, conventions de date, arrondis,
  ventilations). Où définir « la » règle de référence ?

## Décision

- La **définition de référence** de chaque KPI est une fonction Python pure dans
  `backend/src/k_insight/kpi/`, sans dépendance (ni Django, ni DB), **testée avec unittest**.
  C'est le miroir du « domaine financier pur » d'AUGUSTINE.
- Un **catalogue sémantique** (`backend/src/k_insight/semantic/`) déclare chaque métrique
  (clé, unité, maille, direction, mart). Il est la source de vérité du « quoi existe ».
- Le SQL/dbt **matérialise** ces mêmes règles à l'échelle ; un test de réconciliation
  garantit la cohérence (mêmes chiffres sur un échantillon). En cas de divergence,
  **le domaine pur fait foi** et le SQL est corrigé.

## Conséquences

- Les règles métier sont testables en millisecondes, sans infra (cf. 22 tests RH verts).
- Le frontend et l'IA consomment un catalogue unique → pas de KPI « fantôme ».
- Coût : double implémentation (Python + SQL) ; assumé, encadré par la réconciliation.
