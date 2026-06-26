# ADR-0005 — Multi-filiales / multi-entités, RBAC et masquage

- **Statut** : Accepté (2026-06-23)
- **Contexte** : Une seule plateforme pour tout le groupe ; les périmètres de visibilité
  diffèrent (un DRH filiale ≠ un DG groupe ≠ un administrateur CA).

## Décision

- **Chaque fait porte sa filiale et son entité** (`subsidiary_id`, `entity_id`) en
  `warehouse`/`mart`. Pas d'agrégat groupe sans filiale traçable derrière.
- **RBAC applicatif** : rôles (CA, DG groupe, CODIR, DAF, DRH, directeur opérationnel,
  responsable métier, lecteur) × **périmètre** (groupe / liste de filiales / entité).
- **Filtrage systématique** : toute requête au mart est filtrée par le périmètre autorisé
  de l'utilisateur, appliqué côté backend (et idéalement RLS PostgreSQL en défense en profondeur).
- **Masquage de colonnes sensibles** (ex. salaire individuel, données nominatives) selon le
  rôle : agrégats autorisés, détail nominatif restreint.
- **Audit** : toute consultation est journalisée (`audit.access_log` : qui, quoi, quand, périmètre).

## Conséquences

- La dimension `dim_subsidiary` est conforme et obligatoire dans tout fait.
- Le masquage impose un niveau d'agrégation minimal par rôle (paramétrable).
- Historique des consultations exigé par le brief → couvert par l'audit trail.
