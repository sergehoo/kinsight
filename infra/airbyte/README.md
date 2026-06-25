# Airbyte (EL) — déploiement hors `docker-compose`

Conformément à l'**ADR-0003**, Airbyte fait l'**Extract-Load uniquement** : il copie les
sources dans le schéma **`raw`** du PostgreSQL EDW, sans transformation (le « T » est
assuré par dbt : `staging → warehouse → mart`).

Airbyte **n'est pas un service du `docker-compose`** de ce dépôt, pour deux raisons :

1. Depuis mi-2024, **Airbyte OSS n'est plus distribué en `docker-compose`** : il s'installe
   via son propre CLI **`abctl`** (qui provisionne un mini-cluster Kubernetes local `kind`).
2. C'est une plateforme multi-conteneurs lourde ; la maintenir à la main reviendrait à figer
   une version *legacy*.

Le `docker-compose` fournit en revanche **tout ce qu'il faut pour qu'Airbyte se branche** :
le schéma `raw` (créé par le DDL) et un **rôle loader dédié** `kinsight_airbyte`
(provisionné par `infra/postgres/init/00-init-k-insight.sh`, droits `CREATE`/écriture sur
`raw` uniquement).

---

## 1. Installer Airbyte (abctl)

```bash
# macOS / Linux — installe le CLI puis Airbyte en local (Docker requis)
brew install airbytehq/tap/abctl        # ou : curl -LsfS https://get.airbyte.com | bash -s --
abctl local install
abctl local credentials                 # affiche l'URL (http://localhost:8000) + identifiants
```

## 2. Connecter Airbyte à l'EDW (destination Postgres → schéma `raw`)

Lance d'abord la stack du dépôt (le rôle loader et le schéma `raw` sont créés au 1er init) :

```bash
docker compose -f infra/docker-compose.yml up -d kinsight-postgres
```

Dans l'UI Airbyte, crée une **destination « Postgres »** avec :

| Champ        | Valeur                                                              |
|--------------|--------------------------------------------------------------------|
| Host         | `host.docker.internal` (macOS/Windows) — sur Linux : IP de l'hôte¹  |
| Port         | `5432` (ou `POSTGRES_PORT`)                                         |
| Database     | `k_insight_edw` (`EDW_DB_NAME`)                                     |
| Default Schema | `raw`                                                            |
| Username     | `k_insight_airbyte` (`AIRBYTE_DB_USER`)                             |
| Password     | `AIRBYTE_DB_PASSWORD`                                               |

¹ Airbyte (cluster `kind`) et la stack `kinsight-*` sont sur des réseaux Docker distincts :
on passe donc par le **port publié sur l'hôte**, pas par l'alias interne `postgres`.

> Volume Postgres déjà existant ? Le script d'init ne s'exécute qu'au **premier** démarrage.
> Pour ajouter le rôle a posteriori, rejoue le bloc `AIRBYTE_DB_USER` du script, ou
> recrée le volume : `docker compose -f infra/docker-compose.yml down -v`.

## 3. Orchestration

Les **syncs Airbyte** puis `dbt run` / `dbt test` sont déclenchés par **Celery Beat**
(`kinsight-celery-beat`), via l'API Airbyte, et tracés dans le schéma `audit` (ADR-0003).

---

## Alternative : Airbyte « legacy » en `docker-compose`

Si tu tiens à un déploiement 100 % `docker compose`, utilise la version *legacy* d'Airbyte
(images `airbyte/*`, ~8 conteneurs) et raccorde-la au réseau **`kinsight-network`** ; la
destination peut alors viser l'alias interne `postgres:5432`. Non fourni ici par défaut
(version figée, lourd à maintenir) — demande-le si besoin et je l'ajoute.
```
