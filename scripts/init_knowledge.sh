#!/bin/bash

cat > knowledge/executive/group_kpis.md <<'EOF'
# KPI Groupe K-Insight

## RH
- Effectif total
- Masse salariale
- Turnover
- Absentéisme
- Coût RH par filiale
- Productivité par département

## Finance
- Chiffre d'affaires
- Marge brute
- EBITDA
- Cash flow
- Trésorerie disponible
- Créances clients
- Dettes fournisseurs

## Immobilier

- Programmes actifs
- Lots disponibles
- Lots réservés
- Lots vendus
- Taux de commercialisation
- Chiffre d'affaires par programme
- Marge par programme

### Construction

- Taux d'avancement construction (%)
- Taux d'avancement VRD (%)
- Budget consommé (%)
- Budget restant
- Écart budget
- Retard planning
- Coût de construction au m²

### Commercialisation & Encaissements

- Montant total vendu
- Montant encaissé
- Montant restant à encaisser
- Taux de recouvrement
- Taux de paiement clients

### Gouvernance Immobilière

- Ratio Construction / Paiement
- Écart Construction vs Paiement
- Besoin de trésorerie projeté
- Couverture financière du projet
- Valeur hypothécaire du programme
- Valeur hypothécaire des biens vendus
- Valeur hypothécaire des biens disponibles

## Stock
- Valeur du stock
- Rotation stock
- Ruptures
- Équipements disponibles
- Équipements affectés
EOF

cat > knowledge/governance/group_structure.md <<'EOF'
# Structure Groupe

K-Insight est une plateforme de gouvernance et d'intelligence décisionnelle groupe.

Elle consolide les données issues de plusieurs entités :
- Siège
- Filiales
- Programmes immobiliers
- Activités financières
- Activités RH
- Activités commerciales
- Activités de construction
- Activités logistiques

Chaque utilisateur accède aux données selon son périmètre :
- Groupe
- Filiale
- Département
- Programme
- Projet
EOF

cat > knowledge/finance/finance_kpis.md <<'EOF'
# KPI Finance

Les KPI finance permettent d'analyser la performance financière du groupe.

## Indicateurs principaux
- Chiffre d'affaires
- Marge brute
- EBITDA
- Résultat net
- Trésorerie
- Cash flow opérationnel
- Créances clients
- Dettes fournisseurs

## Axes d'analyse
- Par filiale
- Par programme immobilier
- Par période
- Par centre de coût
- Par activité
EOF

cat > knowledge/real_estate/program_lifecycle.md <<'EOF'
# Cycle de vie d'un programme immobilier

Un programme immobilier suit les étapes suivantes :

1. Identification du foncier
2. Étude de faisabilité
3. Budget prévisionnel
4. Lancement commercial
5. Travaux VRD
6. Construction
7. Commercialisation des lots
8. Encaissements clients
9. Livraison
10. Clôture du programme

## KPI principaux
- Nombre de lots
- Lots vendus
- Lots disponibles
- Taux de commercialisation
- Avancement des travaux
- Budget consommé
- Marge prévisionnelle
- Marge réalisée
EOF