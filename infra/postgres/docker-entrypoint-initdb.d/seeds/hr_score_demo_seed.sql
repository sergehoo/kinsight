-- =============================================================================
-- Seed de DÉMONSTRATION — mart.hr_score
-- Valeurs ILLUSTRATIVES (clairement étiquetées « démo »), destinées à montrer le
-- rendu du Human Capital Score tant que les sources réelles (enquêtes engagement,
-- LMS, HSE, revues de perf) ne sont pas branchées. En production, ce seed est
-- remplacé par un modèle dbt alimenté par le Data Warehouse — aucune donnée inventée.
--
-- Couvre 12 mois glissants (2025-07 → 2026-06) × 3 filiales × 9 dimensions.
-- Léger trend haussier mensuel pour illustrer la courbe d'évolution.
-- Usage : psql -d k_insight_edw -f warehouse/ddl/seeds/hr_score_demo_seed.sql
-- =============================================================================

TRUNCATE mart.hr_score;

INSERT INTO mart.hr_score (month_start, subsidiary_code, dimension_key, score)
SELECT
    m.month_start,
    b.subsidiary_code,
    b.dimension_key,
    LEAST(100, ROUND(b.base + (m.idx - 1) * 0.4, 2))::numeric(5, 2) AS score
FROM (
    VALUES
      -- (filiale, dimension, score de base)
      ('KRE', 'effectifs_stabilite', 82), ('KRE', 'presence_ponctualite', 88),
      ('KRE', 'productivite', 79),         ('KRE', 'recrutement', 74),
      ('KRE', 'performance', 81),          ('KRE', 'formation_competences', 70),
      ('KRE', 'engagement_climat', 76),    ('KRE', 'sante_securite', 90),
      ('KRE', 'conformite', 95),
      ('KSH', 'effectifs_stabilite', 78), ('KSH', 'presence_ponctualite', 85),
      ('KSH', 'productivite', 74),         ('KSH', 'recrutement', 70),
      ('KSH', 'performance', 77),          ('KSH', 'formation_competences', 66),
      ('KSH', 'engagement_climat', 72),    ('KSH', 'sante_securite', 93),
      ('KSH', 'conformite', 92),
      ('MYK', 'effectifs_stabilite', 75), ('MYK', 'presence_ponctualite', 80),
      ('MYK', 'productivite', 72),         ('MYK', 'recrutement', 68),
      ('MYK', 'performance', 74),          ('MYK', 'formation_competences', 64),
      ('MYK', 'engagement_climat', 70),    ('MYK', 'sante_securite', 86),
      ('MYK', 'conformite', 90)
) AS b(subsidiary_code, dimension_key, base)
CROSS JOIN (
    SELECT d::date AS month_start,
           row_number() OVER (ORDER BY d) AS idx
    FROM generate_series('2025-07-01'::date, '2026-06-01'::date, '1 month') AS g(d)
) AS m;
