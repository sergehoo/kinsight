-- =============================================================================
-- Seed de DÉMONSTRATION — mart.domain_score (GÉNÉRÉ depuis les cadres vérifiés)
-- Valeurs ILLUSTRATIVES (étiquetées « démo »), pour montrer le rendu du Score de
-- Gouvernance de chaque domaine tant que les sources métier ne sont pas branchées.
-- En production, un modèle dbt par domaine remplace ce seed — aucune donnée inventée.
--
-- 12 mois glissants (2025-07 → 2026-06) × 3 filiales × dimensions de chaque domaine.
-- Léger trend haussier mensuel (+0,4/mois) pour la courbe d'évolution.
-- Usage : psql -d k_insight_edw -f warehouse/ddl/seeds/domain_score_demo_seed.sql
-- =============================================================================

TRUNCATE mart.domain_score;

INSERT INTO mart.domain_score (domain_key, month_start, subsidiary_code, dimension_key, score)
SELECT
    b.domain_key,
    m.month_start,
    b.subsidiary_code,
    b.dimension_key,
    LEAST(100, ROUND(b.base + (m.idx - 1) * 0.4, 2))::numeric(5, 2) AS score
FROM (
    VALUES
      ('immobilier', 'KRE', 'maitrise_fonciere', 82),
      ('immobilier', 'KSH', 'maitrise_fonciere', 79),
      ('immobilier', 'MYK', 'maitrise_fonciere', 76),
      ('immobilier', 'KRE', 'execution_programmes', 75),
      ('immobilier', 'KSH', 'execution_programmes', 72),
      ('immobilier', 'MYK', 'execution_programmes', 69),
      ('immobilier', 'KRE', 'discipline_financiere', 80),
      ('immobilier', 'KSH', 'discipline_financiere', 77),
      ('immobilier', 'MYK', 'discipline_financiere', 74),
      ('immobilier', 'KRE', 'performance_commerciale', 74),
      ('immobilier', 'KSH', 'performance_commerciale', 71),
      ('immobilier', 'MYK', 'performance_commerciale', 68),
      ('immobilier', 'KRE', 'securite_chantier', 81),
      ('immobilier', 'KSH', 'securite_chantier', 78),
      ('immobilier', 'MYK', 'securite_chantier', 75),
      ('immobilier', 'KRE', 'pilotage_risques', 76),
      ('immobilier', 'KSH', 'pilotage_risques', 73),
      ('immobilier', 'MYK', 'pilotage_risques', 70),
      ('finance', 'KRE', 'liquidite_tresorerie', 86),
      ('finance', 'KSH', 'liquidite_tresorerie', 83),
      ('finance', 'MYK', 'liquidite_tresorerie', 80),
      ('finance', 'KRE', 'qualite_poste_clients', 79),
      ('finance', 'KSH', 'qualite_poste_clients', 76),
      ('finance', 'MYK', 'qualite_poste_clients', 73),
      ('finance', 'KRE', 'discipline_budgetaire', 84),
      ('finance', 'KSH', 'discipline_budgetaire', 81),
      ('finance', 'MYK', 'discipline_budgetaire', 78),
      ('finance', 'KRE', 'conformite_fiscale', 78),
      ('finance', 'KSH', 'conformite_fiscale', 75),
      ('finance', 'MYK', 'conformite_fiscale', 72),
      ('finance', 'KRE', 'maitrise_risques_financiers', 85),
      ('finance', 'KSH', 'maitrise_risques_financiers', 82),
      ('finance', 'MYK', 'maitrise_risques_financiers', 79),
      ('finance', 'KRE', 'fiabilite_previsionnelle', 80),
      ('finance', 'KSH', 'fiabilite_previsionnelle', 77),
      ('finance', 'MYK', 'fiabilite_previsionnelle', 74),
      ('operations', 'KRE', 'maitrise_stocks', 78),
      ('operations', 'KSH', 'maitrise_stocks', 75),
      ('operations', 'MYK', 'maitrise_stocks', 72),
      ('operations', 'KRE', 'fiabilite_inventaires', 71),
      ('operations', 'KSH', 'fiabilite_inventaires', 68),
      ('operations', 'MYK', 'fiabilite_inventaires', 65),
      ('operations', 'KRE', 'integrite_achats', 76),
      ('operations', 'KSH', 'integrite_achats', 73),
      ('operations', 'MYK', 'integrite_achats', 70),
      ('operations', 'KRE', 'performance_fournisseurs', 70),
      ('operations', 'KSH', 'performance_fournisseurs', 67),
      ('operations', 'MYK', 'performance_fournisseurs', 64),
      ('operations', 'KRE', 'disponibilite_actifs', 77),
      ('operations', 'KSH', 'disponibilite_actifs', 74),
      ('operations', 'MYK', 'disponibilite_actifs', 71),
      ('operations', 'KRE', 'maitrise_couts', 72),
      ('operations', 'KSH', 'maitrise_couts', 69),
      ('operations', 'MYK', 'maitrise_couts', 66),
      ('operations', 'KRE', 'maitrise_risques_ops', 75),
      ('operations', 'KSH', 'maitrise_risques_ops', 72),
      ('operations', 'MYK', 'maitrise_risques_ops', 69),
      ('commercial-clients', 'KRE', 'fiabilite_donnees_crm', 84),
      ('commercial-clients', 'KSH', 'fiabilite_donnees_crm', 81),
      ('commercial-clients', 'MYK', 'fiabilite_donnees_crm', 78),
      ('commercial-clients', 'KRE', 'maitrise_pipeline', 77),
      ('commercial-clients', 'KSH', 'maitrise_pipeline', 74),
      ('commercial-clients', 'MYK', 'maitrise_pipeline', 71),
      ('commercial-clients', 'KRE', 'conformite_contractuelle', 82),
      ('commercial-clients', 'KSH', 'conformite_contractuelle', 79),
      ('commercial-clients', 'MYK', 'conformite_contractuelle', 76),
      ('commercial-clients', 'KRE', 'maitrise_reclamations', 76),
      ('commercial-clients', 'KSH', 'maitrise_reclamations', 73),
      ('commercial-clients', 'MYK', 'maitrise_reclamations', 70),
      ('commercial-clients', 'KRE', 'tenue_satisfaction_client', 83),
      ('commercial-clients', 'KSH', 'tenue_satisfaction_client', 80),
      ('commercial-clients', 'MYK', 'tenue_satisfaction_client', 77),
      ('commercial-clients', 'KRE', 'fiabilite_previsions_ventes', 78),
      ('commercial-clients', 'KSH', 'fiabilite_previsions_ventes', 75),
      ('commercial-clients', 'MYK', 'fiabilite_previsions_ventes', 72),
      ('risques-conformite', 'KRE', 'maitrise_des_risques', 89),
      ('risques-conformite', 'KSH', 'maitrise_des_risques', 86),
      ('risques-conformite', 'MYK', 'maitrise_des_risques', 83),
      ('risques-conformite', 'KRE', 'conformite_reglementaire', 82),
      ('risques-conformite', 'KSH', 'conformite_reglementaire', 79),
      ('risques-conformite', 'MYK', 'conformite_reglementaire', 76),
      ('risques-conformite', 'KRE', 'posture_securite', 87),
      ('risques-conformite', 'KSH', 'posture_securite', 84),
      ('risques-conformite', 'MYK', 'posture_securite', 81),
      ('risques-conformite', 'KRE', 'assurance_audit', 81),
      ('risques-conformite', 'KSH', 'assurance_audit', 78),
      ('risques-conformite', 'MYK', 'assurance_audit', 75),
      ('risques-conformite', 'KRE', 'gestion_incidents', 88),
      ('risques-conformite', 'KSH', 'gestion_incidents', 85),
      ('risques-conformite', 'MYK', 'gestion_incidents', 82),
      ('risques-conformite', 'KRE', 'exposition_juridique', 83),
      ('risques-conformite', 'KSH', 'exposition_juridique', 80),
      ('risques-conformite', 'MYK', 'exposition_juridique', 77)
) AS b(domain_key, subsidiary_code, dimension_key, base)
CROSS JOIN (
    SELECT d::date AS month_start, row_number() OVER (ORDER BY d) AS idx
    FROM generate_series('2025-07-01'::date, '2026-06-01'::date, '1 month') AS g(d)
) AS m;
