# ADR-0008 — Conventions techniques : UUID v7, BIGINT, XOF entier, UTC

- **Statut** : Accepté (2026-06-23)
- **Contexte** : Cohérence avec l'écosystème du groupe (AUGUSTINE) et exigences analytiques.

## Décision

- **Clés primaires** : UUID v7 pour les entités applicatives. Dans l'EDW, clés de
  substitution entières (`BIGINT` séquentiel) pour les dimensions/faits (perf de jointure),
  + clé naturelle source conservée.
- **Montants** : entiers **`BIGINT`**, devise **XOF** à **0 décimale** (le franc CFA n'a pas
  de subdivision usuelle en gestion). Jamais de `float` sur l'argent — même règle que le
  `Money` d'AUGUSTINE.
- **Temps** : tout en **UTC** en base ; conversion d'affichage au fuseau de la filiale côté
  frontend. `dim_date` (et `dim_time` si besoin) conformes.
- **Dimensions à évolution lente** : SCD type 2 pour `dim_employee`, `dim_subsidiary`
  (historisation des changements d'affectation, de poste).
- **Périodes d'analyse** : bornes **demi-ouvertes** `[start, end[` partout (Python et SQL).

## Conséquences

- Pas de perte de précision financière ; agrégations exactes.
- Les comparaisons inter-filiales en XOF sont directes ; conversions multidevises = ADR futur
  si une filiale hors zone XOF apparaît.
