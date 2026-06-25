# ADR-0003 — Airbyte = EL seul ; dbt-core = transformations

- **Statut** : Accepté (2026-06-23)
- **Contexte** : Le brief cite Airbyte mais pas l'outil de transformation. Où vit le « T » du ELT ?

## Décision

- **Airbyte** fait l'_Extract-Load_ uniquement : il copie les sources dans `raw` sans
  les transformer (incrémental, CDC quand la source le permet). Une table `raw` par flux.
- **dbt-core** assure toutes les transformations `staging → warehouse → mart`, versionnées
  dans `warehouse/dbt/`, avec tests dbt (`not_null`, `unique`, `relationships`) et docs.
- **Aucune transformation métier dans Django.** Django lit des modèles dbt déjà calculés.
- Orchestration : Airbyte (sync) puis `dbt run`/`dbt test` déclenchés par **Celery Beat**
  (le résultat des runs est tracé dans `audit`).

## Conséquences

- Lignage clair, transformations testées et documentées (`dbt docs`).
- La logique de KPI existe à deux endroits (dbt SQL + domaine pur Python) : ils doivent
  rester cohérents ; le domaine pur fait foi sur la sémantique (ADR-0006).
- Rejet de « transformer dans des vues Django/ORM » : non testable, non versionné, lent.
