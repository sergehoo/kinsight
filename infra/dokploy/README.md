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

Seul le **frontend** est exposé par Traefik ; tout le reste reste sur le réseau interne
`kinsight` (pas de port publié).

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
