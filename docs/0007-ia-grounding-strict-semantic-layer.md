# ADR-0007 — IA décisionnelle strictement ancrée sur la couche sémantique

- **Statut** : Accepté (2026-06-23)
- **Contexte** : Le brief veut un copilote (analyse KPI, risques, prévisions, synthèses
  CODIR/CA) qui « ne doit jamais inventer d'informations ». Les LLM hallucinent par défaut.

## Décision

L'IA ne produit **jamais** de chiffre de tête. Pipeline imposé :

1. **Compréhension** : la question est mappée à des **métriques du catalogue** (ADR-0006)
   et à des dimensions/filtres déclarés. Une métrique inconnue → refus explicite, pas d'invention.
2. **Récupération** : génération d'une requête **bornée** (text-to-SQL contraint au mart,
   ou appels d'agrégats pré-définis), exécutée en lecture seule sur `mart`/`analytics`.
3. **Rédaction** : le LLM ne fait que **commenter/synthétiser les chiffres récupérés**,
   avec citation systématique de la source (métrique, période, filiale).
4. **Modèles Claude** (les plus récents et adaptés) pour la synthèse ; prévisions et
   détection d'anomalies par modèles statistiques dédiés, écrits dans `analytics`.

Toute réponse IA est journalisée (question, requêtes exécutées, chiffres servis) dans `audit`.

## Conséquences

- Réponses traçables et reproductibles ; pas de chiffre non sourcé.
- La qualité de l'IA dépend de la richesse du catalogue sémantique → on l'étend par incrément.
- Garde-fou : si la donnée n'existe pas au mart, l'IA répond « non disponible », pas une estimation.
