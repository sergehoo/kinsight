# Déploiement production — Dokploy

Production via **Dokploy** (PaaS auto-hébergé, Docker + Traefik). Le déploiement utilise
un service **Compose** pointant sur [`docker-compose.dokploy.yml`](../../docker-compose.dokploy.yml).

## Architecture servie

```
Internet ──TLS──▶ Traefik (Dokploy, dokploy-network)
                     │  Host(DOMAIN)
                     ▼
                 frontend (nginx :8080)
                     ├─ /            → SPA React
                     ├─ /api/        → proxy ▶ backend:8000   (réseau interne kinsight)
                     ├─ /admin/      → proxy ▶ backend:8000
                     └─ /static/     → fichiers collectés (volume django-static)
backend (gunicorn) ─ postgres (app + EDW) · redis · minio
celery-worker / celery-beat ─ orchestrent Airbyte + dbt
```

Traefik route **trois chemins** sur le même domaine : `/` vers le frontend, `/api` et `/admin`
vers le backend. Aucun port n'est publié ; postgres, redis et minio restent sur le seul réseau
interne `kinsight`.

### Routage à déclarer dans l'onglet « Domains » de Dokploy

| Service | Host | Path | Port | HTTPS |
|---|---|---|---|---|
| `frontend` | `insight.kaydan.tech` | `/` | 8080 | oui |
| `backend` | `insight.kaydan.tech` | `/api` | 8000 | oui |
| `backend` | `insight.kaydan.tech` | `/admin` | 8000 | oui |

Traefik ordonne ses routeurs par longueur de règle : `/api` et `/admin`, plus spécifiques,
passent avant `/`. Aucune priorité à régler à la main. `/static/` reste servi par le frontend,
sous la règle `/` — c'est ce qui habille l'admin Django.

Ne **jamais** ajouter de labels `traefik.*` dans le fichier compose : deux jeux de labels sur un
même conteneur produisent l'erreur « cannot be linked automatically with multiple Services »,
donc un 502.

### Pourquoi les noms internes sont préfixés `kinsight-`

`dokploy-network` est **partagé par tous les projets** de la plateforme. Le résolveur DNS de
Docker répond avec les enregistrements de ce réseau partagé et **ne redescend pas** sur le réseau
privé : tout conteneur attaché aux deux résout donc le service *homonyme d'un autre projet*.

C'est l'origine exacte du 502 de septembre 2026 : le frontend écrivait vers deux « backend »
étrangers, tous deux fermés sur le port 8000, pendant que le backend du projet écoutait
parfaitement. Vérifié en laboratoire — depuis un conteneur bi-attaché, `postgres` résolvait vers
le PostgreSQL d'un autre locataire.

D'où les alias uniques `kinsight-backend`, `kinsight-postgres`, `kinsight-redis`,
`kinsight-minio`, et les variables d'environnement qui les visent. Les alias courts sont
conservés pour les conteneurs qui ne voient que le réseau privé (celery), où il n'y a pas
d'ambiguïté. **Toute nouvelle variable pointant un service interne doit utiliser la forme
préfixée.**

## Pré-requis

- Un serveur avec **Dokploy** installé et un domaine pointant dessus (A/AAAA record).
- Le dépôt accessible par Dokploy (GitHub/GitLab/Git).
- Un certresolver Let's Encrypt actif dans Dokploy (par défaut `letsencrypt`).

## Étapes

1. **Créer le service** : Dokploy → *Create* → **Compose**. Source = ce dépôt, branche `main`.
2. **Compose Path** : `./docker-compose.dokploy.yml`.
3. **Environment** : coller les variables de [`.env.dokploy.example`](../../.env.dokploy.example)
   et renseigner les vraies valeurs (au minimum `DOMAIN` + tous les secrets).
4. **Domaine** : le routage TLS est déjà déclaré via les labels Traefik du service `frontend`
   (Host = `DOMAIN`, redirection HTTP→HTTPS, certresolver `ACME_RESOLVER`). Il suffit que
   `DOMAIN` pointe sur le serveur. *(Alternative : laisser les labels et ne rien ajouter dans
   l'onglet Domains pour éviter un double routage.)*
5. **Deploy**. Au premier démarrage, Postgres crée les bases/rôles + applique le DDL EDW,
   puis le backend joue `migrate` et `collectstatic`.
6. **Créer un admin** (une fois les conteneurs up) via le terminal Dokploy du service backend :
   ```bash
   python manage.py createsuperuser
   ```

## Dépannage — « 502 Bad Gateway » sur /api/ alors que le site s'affiche

Symptôme : `https://DOMAIN/` et `/healthz` répondent 200, `/static/` aussi, mais **tout**
ce qui passe par `/api/` et `/admin/` renvoie 502 — et vite (moins d'une seconde),
pas après un délai. Le corps de la réponse est celui de nginx, pas de Traefik.

Ce n'est pas un dépassement de délai (qui donnerait un 504 après ~60 s) : c'est
`proxy_pass` qui n'arrive pas à ouvrir la connexion vers `backend:8000`.

Deux causes, à départager dans cet ordre :

0. **Collision de noms sur le réseau partagé.** Avant toute autre piste, regarde l'adresse citée
   dans le journal du frontend : si nginx écrit vers une IP qui n'appartient à aucun conteneur du
   projet, c'est qu'il a résolu le service d'un autre locataire. Remède : viser un nom préfixé
   `kinsight-` (voir plus haut).

1. **nginx pointe vers une adresse périmée.** C'est le cas le plus fréquent après
   un redéploiement : le conteneur backend repart avec une nouvelle IP, et un nginx
   qui n'a pas été recréé continue d'écrire vers l'ancienne. Le journal du conteneur
   frontend le dit mot pour mot :

   ```bash
   docker compose logs --tail=50 frontend | grep "connect() failed"
   # connect() failed (111: Connection refused) while connecting to upstream,
   # upstream: "http://172.19.0.2:8000/api/v1/..."
   ```

   Si l'IP citée n'est pas celle du conteneur backend actuel
   (`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <backend>`),
   c'est cette cause. Remède immédiat : recréer le conteneur frontend. Remède durable :
   déjà en place dans [`frontend/web/nginx.conf`](../../frontend/web/nginx.conf) — un
   `resolver 127.0.0.11` et un nom d'hôte passé par variable forcent nginx à
   redemander l'adresse à chaque requête au lieu de la figer au démarrage.

2. **Le backend n'écoute pas.** `migrate`, `collectstatic` ou `gunicorn` a échoué au
   démarrage, et le conteneur boucle :

   ```bash
   docker compose ps backend
   docker compose logs --tail=100 backend
   ```

   Le healthcheck interroge `/healthz/` : un conteneur durablement `unhealthy` signale
   que gunicorn n'a jamais répondu.

Pour trancher la sortie réseau du backend (DNS, TLS, endpoint, jeton), couche par couche :

```bash
docker compose exec backend python manage.py integrations_doctor
```

## Transformations dbt

Service `dbt` en profil opt-in. Depuis le serveur (ou un "Run" Dokploy) :

```bash
docker compose -f docker-compose.dokploy.yml --profile dbt run --rm dbt build
```

En continu, c'est **Celery Beat** qui déclenche Airbyte puis `dbt run`/`dbt test` (ADR-0003).

## Airbyte (EL)

Airbyte se déploie **hors de cette stack** (via `abctl`) et se branche sur l'EDW
(schéma `raw`, rôle `k_insight_airbyte`). Voir [infra/airbyte/README.md](../airbyte/README.md).

## Points production déjà câblés

- **TLS / proxy** : nginx conserve `X-Forwarded-Proto` (Traefik) ; Django est rendu
  proxy-aware via `SECURE_SSL_PROXY=1`, `CSRF_TRUSTED_ORIGINS=https://DOMAIN`,
  cookies sécurisés (`DJANGO_SECURE_COOKIES=1`). `DEBUG=0`, `ALLOWED_HOSTS` inclut `DOMAIN`.
- **Persistance** : volumes nommés `kinsight-*` (postgres, redis, minio, static).
- **Santé** : healthchecks sur postgres, redis, minio, backend (`/healthz/`), frontend (`/healthz`).
- **Pas de noms figés** : ni `name:` projet ni `container_name`, pour laisser Dokploy
  orchestrer plusieurs environnements sans collision.

## Mises à jour

Push sur la branche suivie → **Redeploy** dans Dokploy (rebuild des images backend/frontend,
`migrate`/`collectstatic` rejoués automatiquement).

## Notes / extensions

- **MinIO** reste interne. Pour servir des exports via URL présignée au navigateur, exposer
  MinIO sur un sous-domaine (ajouter des labels Traefik dédiés + `MINIO_BROWSER_REDIRECT_URL`).
- **Observabilité** (Prometheus/Grafana/Loki) : non incluse (incrément DevOps).
