-- =============================================================================
-- MART.HR_SCORE — Human Capital Score (ADR-0006, ADR-0007)
-- Maille : filiale × dimension × mois. `score` ∈ [0, 100] par dimension.
-- La pondération et l'agrégation globale font foi côté domaine pur :
--   backend/src/k_insight/kpi/hr_score.py (HC_DIMENSIONS, human_capital_score).
--
-- ⚠️  Cette TABLE est un RÉCEPTACLE. Les scores par dimension proviennent de
--     sources hétérogènes encore à brancher (enquêtes d'engagement, LMS/formation,
--     incidents HSE, revues de performance…). Tant qu'une dimension n'a pas de
--     source réelle, AUCUNE valeur n'est inventée : la ligne est simplement absente
--     et l'API renvoie N/D (gouverné). En production, un modèle dbt remplacera le
--     seed de démonstration.
-- =============================================================================

CREATE TABLE IF NOT EXISTS mart.hr_score (
    month_start     DATE NOT NULL,
    subsidiary_code TEXT NOT NULL,
    dimension_key   TEXT NOT NULL,          -- clé de HC_DIMENSIONS (kpi/hr_score.py)
    score           NUMERIC(5, 2) NOT NULL CHECK (score >= 0 AND score <= 100),
    PRIMARY KEY (month_start, subsidiary_code, dimension_key)
);

COMMENT ON TABLE mart.hr_score IS
  'Human Capital Score par filiale × dimension × mois (0-100). Pondération : kpi/hr_score.py (ADR-0006). Réceptacle : N/D tant que la source d''une dimension n''est pas branchée (ADR-0007).';
