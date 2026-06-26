# ADR-0002 — EDW PostgreSQL multi-schémas, modélisation Kimball

- **Statut** : Accepté (2026-06-23)
- **Contexte** : Le brief impose les schémas `raw, staging, warehouse, mart, analytics, audit`
  et 13 data marts. Quelle organisation et quelle modélisation ?

## Décision

Un seul PostgreSQL, **schémas par couche** (pas de base par couche) :

| Schéma | Contenu | Mutabilité |
|---|---|---|
| `raw` | copie fidèle des sources (Airbyte), horodatée | append-only |
| `staging` | nettoyé/typé/renommé, 1 modèle par flux | recalculé par dbt |
| `warehouse` | dimensions & faits **conformes** (Kimball, étoile), clés de substitution | recalculé par dbt |
| `mart` | agrégats orientés usage métier (HR_MART…), servis à l'API | recalculé par dbt |
| `analytics` | sorties IA : prévisions, scores d'anomalie, recommandations | écrit par Celery/IA |
| `audit` | journal des consultations, accès, exécutions | append-only |

Modélisation **dimensionnelle Kimball** : dimensions conformes partagées
(`dim_date`, `dim_subsidiary`, `dim_employee`, `dim_department`…) et tables de faits
par processus métier. Les marts réutilisent ces conformes — pas de silos.

## Conséquences

- Réutilisation des dimensions entre marts → cohérence du « groupe ».
- `mart` peut être en tables matérialisées (perf) ou vues (fraîcheur) selon la métrique.
- Sécurité par schéma : le rôle applicatif n'a `SELECT` que sur `mart` (cf. ADR-0004).
