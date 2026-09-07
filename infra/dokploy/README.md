# Déploiement production — Dokploy

Production via **Dokploy** (PaaS auto-hébergé, Docker + Traefik). Le déploiement utilise
un service **Compose** pointant sur [`docker-compose.dokploy.yml`](../../docker-compose.dokploy.yml).

## Architecture servie

```
Internet ──TLS──▶ Traefik (Dokploy, dokploy-network)  ── SEUL reverse proxy
                     │  Host(DOMAIN)
                     ├─ /                  → frontend:8080  (SPA React + /static/)
                     ├─ /api               → backend:8000
                     └─ /manage/app/back   → backend:8000   (admin Django)

frontend (nginx :8080)   ne sert QUE le build React et les fichiers statiques
backend  (gunicorn)      kinsight + dokploy-network, aucun port publié
postgres · redis · minio réseau interne `kinsight` UNIQUEMENT
celery-worker / celery-beat ─ orchestrent Airbyte + dbt
```

Traefik route **trois chemins** sur le même domaine : `/` vers le frontend, `/api` et
`/manage/app/back` (l'admin Django) vers le backend. `/admin/…` appartient au SPA, pas à
Django — les deux se disputaient ce préfixe. Aucun port n'est publié ; postgres, redis et minio restent sur le seul réseau
interne `kinsight`.

### Routage à déclarer dans l'onglet « Domains » de Dokploy

| Service | Host | Path | Port | HTTPS |
|---|---|---|---|---|
| `frontend` | `insight.kaydan.tech` | `/` | 8080 | oui |
| `backend` | `insight.kaydan.tech` | `/api` | 8000 | oui |
| `backend` | `insight.kaydan.tech` | `/manage/app/back` | 8000 | oui |

Traefik ordonne ses routeurs par longueur de règle : `/api` et `/manage/app/back`, plus
spécifiques, passent avant `/`. Aucune priorité à régler à la main. `/static/` reste servi par le frontend,
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

## Dépannage — le routage

Un seul routeur, donc peu de cas possibles. Le corps de la réponse dit qui parle.

**`404 page not found`, sans en-tête `Server`.** C'est Traefik : aucun routeur ne
correspond à la requête. Le conteneur visé est arrêté, ou la règle du domaine manque
dans l'onglet « Domains ».

**Une réponse `503` en texte brut nommant K-Insight.** C'est nginx, et le message le
dit : la règle Traefik `/api` ou `/manage/app/back` n'est pas déclarée, donc le chemin
est arrivé sur le frontend. Ce garde-fou existe pour éviter le pire diagnostic — sans
lui, un appel JSON recevrait la page HTML du SPA avec un code 200.

**Un `502` de Traefik.** Le conteneur cible ne répond pas sur son port. À vérifier
depuis l'hôte :

```bash
docker compose -f docker-compose.dokploy.yml ps backend && docker compose -f docker-compose.dokploy.yml logs --tail=100 backend
```

La dernière ligne tranche : `Listening at: http://0.0.0.0:8000`, une migration figée
sur un verrou, ou une trace d'erreur.

Pour la sortie réseau vers Shield (DNS, TLS, endpoint, jeton), couche par couche :

```bash
docker compose -f docker-compose.dokploy.yml exec backend python manage.py integrations_doctor
```

### Confiance accordée au proxy

Le backend partage `dokploy-network` avec les autres projets de la plateforme. Sans
précaution, un conteneur voisin pourrait écrire `X-Forwarded-For` et `X-Forwarded-Proto`,
donc choisir l'adresse inscrite dans la piste d'audit et le protocole que Django croit
voir. Seul le pair déclaré dans `TRUSTED_PROXY_HOSTS` est cru ; pour tout autre appelant
ces en-têtes sont retirés de la requête et l'adresse retenue est celle du pair lui-même.

Vérifier que le nom du conteneur Traefik est le bon — c'est la seule valeur à régler :

```bash
docker ps --format '{{.Names}}' | grep -i traefik
```

S'il diffère de `dokploy-traefik`, le renseigner dans l'onglet « Environment » de Dokploy.
Laissé vide ou erroné, le système reste sûr mais la piste d'audit retient l'adresse du
proxy au lieu de celle de l'utilisateur — infalsifiable, mais peu informatif.

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
