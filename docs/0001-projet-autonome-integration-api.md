# ADR-0001 — k-insight est un projet autonome, intégré aux autres via API

- **Statut** : Accepté (2026-06-23)
- **Contexte** : Le workspace contient déjà `codir` (gestion des réunions/décisions CODIR,
  comptes-rendus, enregistrements) et des systèmes sources (`RH-oddoo`, `kexpress`).
  Faut-il étendre `codir` ou créer un projet séparé pour la plateforme EDW/BI/IA ?

## Décision

k-insight est un **dépôt autonome**. `codir` reste le pilotage des réunions et décisions ;
k-insight est la plateforme de données et d'intelligence décisionnelle. Les deux
communiquent par **API** (ex. k-insight publie des KPI consommés dans les CR CODIR ;
`codir` peut pousser des décisions à tracer). Aucun couplage de schéma de base.

## Conséquences

- Déploiement, cycle de vie et montée en charge indépendants.
- Frontière nette des responsabilités ; pas de mélange « gestion de réunions » / « data platform ».
- Coût : duplication mineure (auth, design system) — mutualisable plus tard via un paquet partagé.
