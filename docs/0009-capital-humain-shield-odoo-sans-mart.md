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

## Addendum — Score de gouvernance RH (2026-10-15)

Le score lit l'historique K-Insight, plus `mart.hr_score` (que seul un jeu de démonstration alimentait).
La formule pondérée (`k_insight.kpi.hr_score`, 9 dimensions) est inchangée ; les règles ajoutées sont :

- **Présence & ponctualité** = moyenne de deux sous-scores linéaires bornés 0–100 :
  présence (70 % → 0, seuil critique de `shield_rules` ; 95 % → 100) et ponctualité (85 % → 0 ; 99 % → 100).
  Exige les deux taux et au moins 50 % de jours mesurés sur la période.
- Les huit autres dimensions n'ont pas de source dans l'architecture Shield + Odoo : N/D avec leur motif.
- **Score global publié seulement si les dimensions mesurées couvrent au moins 50 % du poids total.** La
  renormalisation seule produirait un « global » à partir de 10 % du poids : un chiffre d'apparence consolidée
  qui ne mesure qu'un dixième de ce qu'il prétend.
- Aucun score par filiale tant que la présence Shield n'est pas rattachée aux filiales.

## Addendum — Graphiques (2026-10-15)

- Un graphe RH lit l'historique K-Insight (`/governance/hr/history/`) sous les filtres du cockpit et le périmètre
  serveur. Le type suit la donnée : courbe (tendance), barres (sites, départements), donut (structure), barres
  empilées (employés / ouvriers, `matrice=type`), carte de chaleur (jours × sites, `matrice=site`).
- La matrice SUIT les filtres : un filtre site restreint ses lignes ; un filtre sur l'autre dimension la rend
  impossible (le croisement site × type n'est pas historisé) et le serveur le dit (`matrice_motif`). Elle est
  bornée à 92 jours. Une ventilation non servie porte de même son `ventilation_motif`.
- La carte de chaleur est colorée par les seuils **publiés** avec la mesure (`seuils`, `shield_rules`) :
  critique / surveillance / normal. Une case non mesurée reste vide.
- Les sections du catalogue qu'aucune source ne sert ne rendent plus de cadre de graphe vide : elles sont
  listées « sans source » avec leur motif (`frontend/web/src/config/graphesRh.ts`).

## Addendum — Signaux et seuils arbitrés (2026-10-15)

- **Neuf signaux** (`backend/apps/governance/signaux_rh.py`), évalués sur la période filtrée, sous le périmètre
  serveur : présence faible, absentéisme (absences pointées — l'absentéisme mensuel n'est pas mesuré), retards
  élevés, site en sous-effectif, effectif critique (baisse de l'effectif déclaré vs période précédente), et
  quatre signaux sans source (turnover, contrats à échéance, recrutement sous cible, heures supplémentaires).
  États : normal / surveillance / critique / **non mesuré** — jamais « normal » sans mesure.
- Chaque signal publie sa règle écrite, ses seuils (par défaut ou arbitrés), la comparaison à la période
  précédente, la source, la couverture et une confiance qui en découle (≥ 80 % de jours mesurés : élevée ;
  ≥ 50 % : moyenne ; sinon faible).
- **Seuils configurables** (`SeuilRh`, API `PUT /governance/hr/seuils/`) : seules les surcharges sont stockées ;
  l'ordre des paliers est imposé par le sens du signal ; chaque arbitrage est tracé (avant / après). Droit
  d'arbitrage : DRH à périmètre Groupe et administration ; les autres lisent.
- **Une seule source de vérité** : les surcharges remontent dans `shield_rules.seuils_publics()` — constats du
  jour, carte de chaleur et signaux jugent avec les mêmes bornes ; la charge Shield en cache est oubliée après
  un arbitrage. Le barème du score de gouvernance, lui, garde ses constantes.
- Les douze lignes d'alertes écrites en dur du centre d'alertes RH sont retirées.

## Addendum — Aide à la décision RH (2026-10-15)

- `HRDecisionEngine` (`backend/apps/governance/decision_rh.py`) : **données réelles → calculs déterministes →
  IA → synthèse**. Les constats sont des règles écrites sur l'historique (signaux hors zone normale, sites à
  ≥ 10 pts sous le Groupe, retards concentrés à ≥ 50 % sur 3 sites dès 4 sites, variation de présence ≥ 3 pts,
  historique < 50 % de jours mesurés), avec valeur, comparaison, période, source, confiance, exploration et
  action recommandée écrite. Trois à sept par criticité ; **jamais complétés pour atteindre un quota**.
- La synthèse (`GET /governance/hr/decision/?synthese=1`, sur demande) est rédigée par le routeur IA existant à
  partir des seuls constats. **Garde-fou** : toute phrase contenant un nombre absent des constats est retirée ;
  les causes sont préfixées « Hypothèse : ». Sans modèle, la synthèse est composée des constats et le dit.
- Périmètre : un utilisateur restreint ne reçoit aucun constat tiré des chiffres Groupe de Shield ; ses angles
  morts deviennent des questions à investiguer.
