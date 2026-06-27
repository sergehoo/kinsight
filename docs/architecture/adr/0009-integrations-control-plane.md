# ADR-0009 — Control-plane d'intégration dynamique, source-agnostic

- **Statut** : Accepté (2026-06-26)
- **Contexte** : Toutes les plateformes sources (K-Shield, K-Express, CRM, Stocks, Finance…)
  ne sont pas prêtes. K-Insight doit fonctionner sans elles et permettre d'ajouter/configurer
  une source **depuis l'admin, sans modifier le code**.

## Décision

- Un app Django **`integrations`** sert de **control-plane** : il stocke la *configuration*
  et l'*état* des connecteurs, jamais la donnée analytique. Modèles : `DataSource`,
  `DataConnector`, `ConnectorEndpoint`, `ConnectorCredential`, `FieldMapping`, `SyncJob`,
  `SyncLog`, `SyncError`, `WebhookEvent`.
- **Source-agnostic** : le flux reste `source → connecteur → Airbyte/ETL → EDW → Django → React`.
  Le frontend n'appelle JAMAIS une API externe (réaffirme ADR-0004). `sync-now` déclenchera
  l'ETL (Airbyte) ; tant qu'il n'est pas branché, le job est journalisé sans ingestion directe.
- **Types supportés** : REST, GraphQL, Webhook, PostgreSQL/MySQL (lecture seule), CSV, Excel,
  Google Sheets, Airbyte. Config 100 % via API/admin (URL, endpoints, auth, headers, fréquence,
  mapping, module cible).
- **Sécurité** : secrets **chiffrés at-rest** (chiffrement authentifié stdlib : keystream
  HMAC-SHA256 + encrypt-then-MAC ; `cryptography`/KMS en prod) ; **jamais réaffichés en clair**
  (write-only + masqué `••••xxxx`) ; accès réservé **SUPER_ADMIN / ADMIN_INTÉGRATION** ;
  chaque modification journalisée (`audit.AccessLog`).
- **États** d'une source : non configurée, configurée, en test, connectée, synchronisation,
  erreur, désactivée.
- **Mode dégradé** : `demo_mode` par source — une source non connectée affiche « non connectée »
  / données de démonstration et **ne bloque jamais** la plateforme.

## Conséquences

- Quand une plateforme est prête, il suffit de renseigner ses APIs/endpoints dans l'UI pour
  activer la liaison et alimenter l'EDW — aucune release.
- L'exécution réelle de l'ETL (Airbyte) et les éditeurs UI d'endpoints/mapping/logs restent à
  brancher (l'API existe : `/integrations/endpoints|mappings|jobs|logs|errors`).
- En prod, remplacer le chiffrement stdlib par un gestionnaire de secrets (Vault/KMS).
