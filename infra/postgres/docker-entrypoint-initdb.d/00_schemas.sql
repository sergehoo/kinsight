-- =============================================================================
-- k-insight EDW — schémas de la plateforme (ADR-0002)
-- À exécuter sur le PostgreSQL de l'Enterprise Data Warehouse.
-- NOTE : non exécuté ici (aucune instance Postgres dans cet environnement) ;
--        DDL à valider sur une instance réelle.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS raw;        -- copie fidèle des sources (Airbyte), append-only
CREATE SCHEMA IF NOT EXISTS staging;    -- nettoyé / typé / renommé (dbt)
CREATE SCHEMA IF NOT EXISTS warehouse;  -- dimensions & faits conformes (Kimball)
CREATE SCHEMA IF NOT EXISTS mart;       -- agrégats orientés usage métier (servis à l'API)
CREATE SCHEMA IF NOT EXISTS analytics;  -- sorties IA : prévisions, anomalies, recommandations
CREATE SCHEMA IF NOT EXISTS audit;      -- journalisation (accès, consultations, runs)

COMMENT ON SCHEMA raw IS 'Données brutes des sources (Airbyte). Jamais modifiées.';
COMMENT ON SCHEMA staging IS 'Nettoyage/typage/renommage. Recalculé par dbt.';
COMMENT ON SCHEMA warehouse IS 'Dimensions et faits conformes (Kimball). Recalculé par dbt.';
COMMENT ON SCHEMA mart IS 'Agrégats métier servis au backend (lecture seule).';
COMMENT ON SCHEMA analytics IS 'Sorties du moteur IA (prévisions, scores).';
COMMENT ON SCHEMA audit IS 'Audit trail : accès, consultations, exécutions de pipelines.';
