-- =============================================================================
-- k-insight EDW — rôles & sécurité (ADR-0004, ADR-0005)
-- Le backend Django n'a accès QU'au mart (SELECT) et à analytics (SELECT),
-- plus INSERT sur audit. Il ne voit jamais raw / staging / warehouse.
-- NOTE : non exécuté ici ; à valider/adapter sur l'instance Postgres réelle.
-- =============================================================================

-- Rôle applicatif backend (lecture seule analytique)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'k_insight_app') THEN
    CREATE ROLE k_insight_app LOGIN PASSWORD 'change-me-in-secret-manager';
  END IF;
END$$;

-- Lecture seule sur mart et analytics
GRANT USAGE ON SCHEMA mart, analytics TO k_insight_app;
GRANT SELECT ON ALL TABLES IN SCHEMA mart, analytics TO k_insight_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA mart, analytics
  GRANT SELECT ON TABLES TO k_insight_app;

-- Écriture de l'audit trail uniquement
GRANT USAGE ON SCHEMA audit TO k_insight_app;
GRANT INSERT, SELECT ON ALL TABLES IN SCHEMA audit TO k_insight_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit
  GRANT INSERT, SELECT ON TABLES TO k_insight_app;

-- Interdiction explicite des couches internes
REVOKE ALL ON SCHEMA raw, staging, warehouse FROM k_insight_app;

-- Rôle de transformation (dbt) — séparé, avec droits d'écriture sur les couches calculées
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'k_insight_dbt') THEN
    CREATE ROLE k_insight_dbt LOGIN PASSWORD 'change-me-in-secret-manager';
  END IF;
END$$;
GRANT USAGE, CREATE ON SCHEMA staging, warehouse, mart TO k_insight_dbt;
GRANT USAGE ON SCHEMA raw TO k_insight_dbt;
GRANT SELECT ON ALL TABLES IN SCHEMA raw TO k_insight_dbt;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw GRANT SELECT ON TABLES TO k_insight_dbt;

-- =============================================================================
-- Table d'audit des consultations (exigée par le brief : historique des consultations)
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit.access_log (
    id              BIGSERIAL PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id         UUID NOT NULL,
    user_role       TEXT NOT NULL,
    action          TEXT NOT NULL,          -- 'view_dashboard', 'query_metric', 'ai_query', 'export'
    metric_key      TEXT,                   -- métrique consultée (catalogue sémantique)
    subsidiary_scope TEXT[],                -- périmètre filiales appliqué
    payload         JSONB,                  -- détails (filtres, requête IA, chiffres servis)
    ip_address      INET
);
COMMENT ON TABLE audit.access_log IS 'Historique des consultations / accès (ADR-0005).';
