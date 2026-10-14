# ADR-0009 — Capital Humain : Shield + Odoo, sans mart EDW obligatoire

- **Statut** : accepté
- **Date** : 2026-10-14
- **Décideur** : direction du projet K-Insight
- **Révise** : ADR-0003 (Airbyte EL + dbt) et ADR-0004 (backend lit le mart en lecture seule), pour le seul domaine Capital Humain

## Contexte

Les écrans RH ont été conçus quand le mart EDW (`mart.hr_*`) était la source attendue. Un inventaire en
lecture seule du dépôt (huit audits indépendants, octobre 2026) a constaté :

- sous Dokploy, les tables du mart **n'existent pas** (le script d'initialisation cherche `ddl/marts/…`, le
  dossier monté contient `marts/` à la racine) : `ModuleDataView` et `build_group_report` répondaient 500 ;
- ailleurs, un mart vide produisait **0** sous l'étiquette « Donnée EDW », et un seed de démonstration
  s'affichait « Données EDW — réel » ;
- le même chiffre avait jusqu'à **six définitions** (effectif total), quatre pour l'absentéisme, quatre pour
  le turnover ; des KPI servis par Shield s'affichaient N/D sur d'autres écrans ;
- plusieurs voies servaient des **totaux Groupe à des utilisateurs restreints à une filiale**.

## Décision

1. **Architecture réelle du Capital Humain** : Kaydan Shield (présence, effectifs déclarés, sites) + Odoo RH
   (référentiel) + PostgreSQL (historique K-Insight) + Redis (cache partagé, single-flight) + Celery
   (collecte périodique). Le mart EDW n'est plus une condition d'aucun écran RH. Ses modèles et son DDL sont
   **conservés**, simplement plus requis.

2. **Registre canonique** (`backend/apps/governance/hr_registry.py`) : une métrique = un identifiant stable
   (`hr.effectif_total`), une source réelle (Shield, Odoo ou **aucune**), une définition, un drapeau
   `instant` pour les mesures « aujourd'hui ». Une métrique sans source porte obligatoirement son **motif**,
   affiché tel quel. Les connecteurs apposent l'identifiant sur leurs charges ; le frontend fusionne par
   identifiant. Aucune valeur par défaut, aucun repli sur 0 (ADR-0007).

3. **Périmètre serveur** :
   - Shield ne rattache pas ses sites aux filiales : **ses totaux sont des totaux Groupe**, servis au seul
     périmètre Groupe. Un périmètre restreint reçoit l'état `disconnected` et le motif, jamais un chiffre
     Groupe ni une attribution inventée. Cela vaut pour les KPI, la série de présence, la sécurité et la vue
     Groupe — y compris les constats globaux, ce qui retourne une décision antérieure (un taux Groupe agrège
     les autres filiales).
   - Odoo est restreint par la **correspondance société ↔ filiale déclarée** dans le centre de connecteurs ;
     sans société déclarée pour une filiale, rien n'est servi (« aucune » n'est pas « toutes »).
   - L'effectif est une donnée RH : il exige le domaine Capital Humain, même dans la vue Groupe.

4. **Cache** : seules des charges de niveau Groupe sont mises en cache (Redis, 60 s Shield, 120 s Odoo),
   avec single-flight inter-processus ; la restriction est appliquée après, par requête. La clé Odoo porte
   le périmètre sociétés.

5. **Seuils** : un seul lieu, `shield_rules`, publiés dans la charge (`seuils`) ; le frontend ne garde qu'un
   repli identique.

## Conséquences

- Un RH de filiale ne voit aucune donnée Shield tant que les sites ne sont pas rattachés aux filiales : c'est
  l'état honnête, et il est dit à l'écran.
- Les métriques de flux (entrées, sorties, turnover, absentéisme mensuel, masse salariale) restent N/D
  légitimes jusqu'à la lecture des dates Odoo et de la paie — avec leur motif.
- Les filtres de période ne s'appliquent aux mesures Shield/Odoo qu'une fois l'historique PostgreSQL en
  place (lot 2) ; d'ici là, les mesures « aujourd'hui » le disent.
