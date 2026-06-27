-- =============================================================================
-- MART.DOMAIN_SCORE — Score de Gouvernance générique par domaine (ADR-0006, ADR-0007)
-- Maille : domaine × filiale × dimension × mois. `score` ∈ [0, 100] par dimension.
-- Les dimensions et pondérations de chaque domaine font foi côté domaine pur :
--   backend/src/k_insight/kpi/domain_scores.py (DOMAIN_SCORES) + score.py (weighted_score).
--
-- ⚠️  RÉCEPTACLE générique (même principe que mart.hr_score). Les scores par dimension
--     proviennent de sources métier encore à brancher (chantiers, finance, ops, CRM,
--     audit…). Tant qu'une dimension n'a pas de source réelle, la ligne est ABSENTE et
--     l'API renvoie N/D (gouverné, ADR-0007) — aucune valeur inventée. En production,
--     un modèle dbt par domaine remplace le seed de démonstration.
-- =============================================================================

CREATE TABLE IF NOT EXISTS mart.domain_score (
    domain_key      TEXT NOT NULL,          -- ex: immobilier, finance, operations…
    month_start     DATE NOT NULL,
    subsidiary_code TEXT NOT NULL,          -- KRE, KSH, MYK
    dimension_key   TEXT NOT NULL,          -- clé de DOMAIN_SCORES[domain] (domain_scores.py)
    score           NUMERIC(5, 2) NOT NULL CHECK (score >= 0 AND score <= 100),
    PRIMARY KEY (domain_key, month_start, subsidiary_code, dimension_key)
);

COMMENT ON TABLE mart.domain_score IS
  'Score de Gouvernance par domaine × filiale × dimension × mois (0-100). Pondérations : kpi/domain_scores.py (ADR-0006). Réceptacle : N/D tant que la source d''une dimension n''est pas branchée (ADR-0007).';
