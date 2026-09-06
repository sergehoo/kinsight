# K-Insight — Progress

Maj : 2026-09-06

## DONE

### Socle UI gouverné (mutualisé, réutilisable)
`components/ui/kit.tsx` — vocabulaire d'états **unique** partagé par tous les domaines et toutes les sources :
`connected | connecting | partial | disconnected | error`.
- `MetricCard` : valeur animée (réutilise `AnimatedNumber`, respecte `prefers-reduced-motion`), squelette pendant la synchro, badge d'état, message explicite, ligne `source · fraîcheur · périmètre`. N'affiche une valeur QUE si la source l'a renvoyée.
- `StateBadge`, `Skeleton` (shimmer CSS), `SourceMeta` + `useRelativeTime` (« il y a X », s'actualise seul toutes les 15 s), `EmptyChartState` (état vide premium + CTA), `IconButton` (tap ≥44 px), `ResponsiveGrid`, `SignalCard`.
- Keyframes `ki-shimmer` / `ki-sync-dot` dans `index.css`, neutralisées sous `prefers-reduced-motion`.

### Corrections de vrais défauts (constatés sur les captures de prod)
1. **Top-nav sous les boutons d'action** : le nav était en `position:absolute` avec une largeur réservée trop courte → il passait sous les actions. Il devient un flex qui rétrécit et défile chez lui. Plus de recouvrement possible, à aucune largeur.
2. **Fausse donnée affichée comme réelle** : `DetailCard` rendait `<Gauge value={8} />` — le « 8 % » présent sur toutes les cartes était **codé en dur** à côté du « N/D ». Composant supprimé, remplacé par le `MetricCard` partagé.
3. **Carte vedette recouvrant le hero** : le texte est borné à `calc(100% - 320px)` sur lg+. Mesuré à 1440 px : hero 321→989, texte 321→**669**, carte à partir de 697 → aucun chevauchement.
4. **Graphe décoratif** : l'histogramme orange s'affichait sans données. Remplacé par `EmptyChartState` gouverné.
5. **Copilot flottant masquant le contenu** en mobile → `pb-28` sous `sm`.
6. **Panne du mart = HTTP 500** : `OperationalError` psycopg remontait telle quelle ; si l'EDW tombait, **toutes les pages domaine cassaient**. Nouveau `MartUnavailable` + `fetch_or_unavailable` → réponse 200 gouvernée (`available:false`, `source_state:"error"`, scores `null`). Vérifié en réel : 500 → 200.
7. **Statut global Shield trompeur** : `connected` était renvoyé même si une partie des appels échouait → devient `partial`.

### Temps réel
- `SyncIndicator` dans le header : état RÉEL du control-plane (`/integrations/sources/health/`), rafraîchi toutes les 60 s. Vérifié en live : « Partiel 1/5 ».
- KPI RH Shield rafraîchis toutes les 120 s, sans rechargement de page.
- Transition douce au changement de domaine (`key={module.id}` → les animations d'entrée rejouent).

### Données
- **Kaydan Shield** (branché) : `shield.py`, endpoints RÉELS `/employees/employees/`, `/ouvriers/workers/`, `/sites/sites/`, `/attendance/summary/today/`. API : `GET /api/v1/integrations/shield/hr-kpi/`. Secret sélectionné de façon déterministe (`_pick_secret`).
- **HMAC Shield = hors périmètre (décidé)** : réservé aux terminaux IoT/casques BLE ; les endpoints back-office lus sont en `jwtAuth`/`cookieAuth` → **Bearer JWT est l'auth correcte**. Schéma de signature non documenté : ne pas l'inventer.
- **Odoo** : squelette inerte `odoo.py` — `not_configured`/`not_implemented`, entités déclarées par domaine (RH : employee/department/job/attendance/leave/applicant ; finance ; opérations). Aucun appel, aucune donnée simulée.
- Identité : `Person` + `ExternalIdentity` (source=`kaydan_shield`). `SourceType` += `kaydan_shield`/`odoo_hr`.

## TESTS
- Backend : **156/156 OK** (154 existants + 2 nouveaux sur la dégradation du mart ; suite Shield 20/20 dont le chemin *connected* prouvé : effectif 200 = 120+80, taux 75,0 %, zéro réel préservé, panne partielle sans valeur inventée).
- Frontend : `tsc --noEmit` + `vite build` verts.
- Visuel réel (backend + front lancés localement) : 1440 / 768 / 390 / 320 px. **Zéro scroll horizontal** mesuré à 320, 390 et 768.

## NEXT
1. **Déployer** : le site en ligne tourne encore sur un build antérieur (colonne CH toujours en « Turnover / Masse salariale · MART À CONNECTER »).
2. Créer la DataSource `kaydan-shield` + credential `api_token` → statut CONNECTED → KPIs live.
3. Répartition par site (`by_site`) sur la forme réelle de `/sites/sites/`.
4. Séries temporelles des graphes (aucun domaine n'en publie encore).
5. Odoo réel (transport XML-RPC/JSON-RPC ou Airbyte).

## BLOCKERS
- URL de base + token Shield réels manquants pour valider `connected` en conditions réelles.
- EDW non lancé localement (normal) — désormais dégradé proprement au lieu de 500.
