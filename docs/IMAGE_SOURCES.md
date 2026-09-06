# Visuels métier K-Insight — provenance et licences

Maj : 2026-09-06

## ⚠️ Point d'attention juridique — à trancher avant mise en production

Les visuels actuellement en place étaient déjà dans le dépôt. **Leur provenance
n'est pas documentée et leur licence n'a pas pu être vérifiée.** Deux d'entre eux
portent des noms de fichier caractéristiques de banques d'images payantes :

| Fichier | Indice de provenance | Risque |
|---|---|---|
| `—Pngtree—modern yellow construction crane for_20885637.png` | Le préfixe `—Pngtree—` et l'identifiant `20885637` correspondent au nommage de Pngtree | Pngtree impose une licence payante ou une attribution pour tout usage commercial |
| `businesswoman-holding-folder-smiling-camera.jpg` | Nommage descriptif typique de Freepik | Freepik gratuit exige une attribution ; sans elle, usage commercial non conforme |
| `tree-grows-coin-glass-jar-with-copy-space.jpg` | Idem | Idem |
| `african-man-holding-ipad.png`, `group-afro-americans-working-together.jpg`, `9315943.png`, `11005799.png` | Non utilisés par un héros aujourd'hui | Provenance inconnue |

**Recommandation** : faire confirmer par l'équipe qui les a ajoutés qu'une licence
commerciale a bien été acquise, ou les remplacer. Ce document n'affirme aucune
licence qui n'aurait pas été constatée.

## Historique — première tentative (bloquée)

La recherche de photos sous licence vérifiable a été tentée depuis cet
environnement, sans succès :

| Source | Résultat | Détail |
|---|---|---|
| Unsplash (recherche) | **HTTP 401** | `unsplash.com/napi/search` et la page publique exigent désormais une autorisation |
| Unsplash (CDN image) | HTTP 200 | Accessible uniquement si l'identifiant de la photo est déjà connu |
| Pexels | **HTTP 403** | Accès refusé sans clé d'API |
| Openverse | **HTTP 502** | Service indisponible |
| Wikimedia Commons | HTTP 200 | Fonctionne et expose la licence, mais son corpus est encyclopédique : photo d'Abidjan de 1900, chantier ferroviaire allemand, personnalités politiques identifiables. Incompatible avec la direction artistique « corporate premium » demandée, et inapproprié en visuel décoratif. |

Aucune image n'a donc été téléchargée. Deviner des identifiants Unsplash de
mémoire aurait permis de récupérer des fichiers, mais **l'auteur et la licence
associés auraient été inventés** — exactement ce que la règle interdit. Aucune
image IA n'a été générée, aucun lien externe n'a été posé.

**Pour débloquer** : une clé d'API Unsplash (gratuite,
`unsplash.com/developers`) ou Pexels (`pexels.com/api`) suffit. Avec elle, la
recherche par métier, la sélection sur 3–5 candidats et l'enregistrement
vérifié de l'auteur et de la licence deviennent automatisables.

## Optimisation livrée

Les visuels en place sont désormais servis en variantes responsives, générées
dans `public/assets/opt/` et rendues par `components/chrome/HeroImage.tsx`
(`<picture>` AVIF → WebP → fichier d'origine en repli).

| Domaine | Variantes | Poids source | Poids servi (1024, AVIF) |
|---|---|---|---|
| Immobilier | `immobilier-crane-{640,1024,1600}.{avif,webp}` | 13,4 Mo | **143 Ko** |
| Capital Humain | `capital-humain-equipe-{640,960}.{avif,webp}` | 57 Ko (photo CC0, voir plus bas) | **32 Ko** |
| Finance | `finance-tresorerie-{640,1024,1600}.{avif,webp}` | 7,1 Mo | **23 Ko** |

Les deux visuels hérités passent de 20,5 Mo de sources à 1,3 Mo de variantes ; le
troisième a été remplacé par une photo CC0 vérifiée (voir plus bas).
Le héros porte `fetchpriority="high"` et `loading="eager"` (il est le LCP) ;
tout autre visuel passe en `loading="lazy"`. Chaque image porte un `alt`
descriptif, et une variante manquante fait automatiquement repli sur l'original.

Les domaines Overview, Opérations, Commercial et Risques n'ont pas de photo :
ils utilisent une illustration vectorielle intégrée. Rien n'a été inventé pour
les combler.

## Procédure à suivre une fois la clé d'API disponible

1. Rechercher 3 à 5 candidats par métier selon les intentions définies
   (skyline groupe, chantier haut de gamme, équipes, finance corporate,
   logistique, réunion commerciale, sécurité/contrôle).
2. Retenir celui dont le sujet est décalé à droite, pour préserver la lisibilité
   du texte de héros à gauche.
3. Télécharger dans `public/assets/`, régénérer les variantes, et consigner ici
   pour chaque image : URL de la photo, auteur, licence, date de récupération.

## Photo intégrée — Capital Humain

| Champ | Valeur |
|---|---|
| Fichier | `public/assets/capital-humain-equipe-stocksnap.jpg` |
| Titre | Team Meeting |
| Auteur | Startup Stock Photos |
| Source | StockSnap.io |
| Page d'origine | https://stocksnap.io/photo/team-meeting-VQXYE2ZEHC |
| Licence | **CC0 1.0** (domaine public — aucune attribution imposée, usage commercial autorisé) |
| Vérification | Métadonnées de licence fournies par l'API Openverse (`api.openverse.org/v1/images/`), qui indexe StockSnap. Identifiant Openverse conservé dans l'historique de recherche. |
| Récupérée le | 2026-09-06 |
| Résolution source | 960 × 640 (la page StockSnap répond 403 hors navigateur ; seule la variante 960 px du CDN est accessible) |
| Variantes | `capital-humain-equipe-{640,960}.{avif,webp}` — pas de 1024/1600 : agrandir une source de 960 px la dégraderait sans rien apporter |
| Cadrage | `object-position: right` — le cadre du héros est presque carré (428 × 430) alors que la photo est en 3:2 ; un recadrage centré amputait le sujet principal |

Cette photo **remplace** `businesswoman-holding-folder-smiling-camera.jpg`, dont la
licence n'était pas documentée (voir le risque juridique ci-dessus). C'est donc à
la fois un gain éditorial et la suppression d'une exposition.

## Les six autres métiers : rien d'intégré, et pourquoi

Une recherche a bien été menée pour chacun via Openverse (licences CC0, domaine
public et CC-BY uniquement — SA et ND écartés, incompatibles avec un produit
propriétaire qui redimensionne). Les candidats ont été téléchargés et **regardés**,
pas jugés sur leurs métadonnées. Verdict :

| Métier | Ce que le corpus propose | Décision |
|---|---|---|
| Overview | Skylines amateurs en 1024 px, ciels gris | Écarté — en dessous de l'existant |
| Immobilier | Grues sur ciel, correct mais amateur et 1024 px | Écarté — le visuel actuel est meilleur |
| Finance | Diagramme d'enquête criminelle avec portraits, stylos sur papier, vieille carte | Écarté — hors sujet |
| Opérations | Conteneurs maritimes photographiés au bord de route | Écarté — qualité amateur |
| Commercial | Poignées de main officielles, **personnalités politiques identifiables** devant des drapeaux | Écarté — hors sujet et droit à l'image |
| Risques | Armoire électrique, salle de contrôle avec **militaires identifiables** | Écarté — hors sujet et droit à l'image |

Intégrer ces images aurait dégradé la direction artistique et rompu la cohérence
demandée entre métiers. Deux d'entre elles posaient en outre un problème de droit
à l'image : une licence CC couvre la photographie, pas l'usage commercial de
l'apparence des personnes qui y figurent.

## Sources testées

| Source | Résultat |
|---|---|
| **Openverse** | ✅ Fonctionne (`api.openverse.org`). Licences vérifiées à la source. Corpus surtout Flickr : très inégal hors CC0 StockSnap. |
| Unsplash | ❌ Anti-bot (« Making sure you're not a bot! »). Non contourné : ce serait un contournement de détection. |
| Pexels | ❌ 403 sans clé d'API |
| Pixabay | ❌ Clé d'API requise |
| Wikimedia Commons | ⚠️ Fonctionne, mais corpus encyclopédique inadapté |

**Pour aller plus loin** : une clé Unsplash ou Pexels (gratuites) ouvrirait un
corpus réellement premium et permettrait de traiter les six métiers restants avec
la même rigueur de licence.
