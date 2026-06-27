-- =============================================================================
-- Seed RAW Airbyte-shaped (Odoo RH) — DÉMONSTRATION / test de la transformation dbt.
-- Reproduit EXACTEMENT le jeu vérifié du domaine pur (5 employés, 12 bulletins Q1 2026)
-- mais au format `raw` produit par Airbyte. Permet de valider raw → staging → mart sans
-- credentials Odoo. Après transformation, mart.hr_kpi (chemin dbt) doit donner pour Q1 2026 :
--   masse salariale = 3 110 000 XOF (KRE 2 150 000 / KSH 960 000), entrées 1 (E4), sorties 2 (E2,E5).
-- =============================================================================

TRUNCATE raw.odoo_hr_employee, raw.odoo_hr_payslip;

INSERT INTO raw.odoo_hr_employee (id, name, subsidiary_code, department_code, date_hired, date_departure, _airbyte_extracted_at) VALUES
  (1, 'Awa Koné',      'KRE', 'OPS', '2025-01-01', NULL,        '2026-04-01T00:00:00Z'),
  (2, 'Bakary Touré',  'KRE', 'OPS', '2025-06-01', '2026-03-15','2026-04-01T00:00:00Z'),
  (3, 'Cica Yao',      'KSH', 'SEC', '2024-03-01', NULL,        '2026-04-01T00:00:00Z'),
  (4, 'Daouda Bamba',  'KSH', 'SEC', '2026-02-01', NULL,        '2026-04-01T00:00:00Z'),
  (5, 'Esther Diallo', 'KRE', 'FIN', '2023-01-01', '2026-01-10','2026-04-01T00:00:00Z');

INSERT INTO raw.odoo_hr_payslip (id, employee_id, subsidiary_code, department_code, date_from, gross_amount, net_amount, employer_charges, _airbyte_extracted_at) VALUES
  (101, 1, 'KRE', 'OPS', '2026-01-01', 300000, 240000, 60000, '2026-04-01T00:00:00Z'),
  (102, 2, 'KRE', 'OPS', '2026-01-01', 250000, 200000, 50000, '2026-04-01T00:00:00Z'),
  (103, 3, 'KSH', 'SEC', '2026-01-01', 200000, 160000, 40000, '2026-04-01T00:00:00Z'),
  (104, 5, 'KRE', 'FIN', '2026-01-01', 500000, 400000, 100000, '2026-04-01T00:00:00Z'),
  (105, 1, 'KRE', 'OPS', '2026-02-01', 300000, 240000, 60000, '2026-04-01T00:00:00Z'),
  (106, 2, 'KRE', 'OPS', '2026-02-01', 250000, 200000, 50000, '2026-04-01T00:00:00Z'),
  (107, 3, 'KSH', 'SEC', '2026-02-01', 200000, 160000, 40000, '2026-04-01T00:00:00Z'),
  (108, 4, 'KSH', 'SEC', '2026-02-01', 180000, 144000, 36000, '2026-04-01T00:00:00Z'),
  (109, 1, 'KRE', 'OPS', '2026-03-01', 300000, 240000, 60000, '2026-04-01T00:00:00Z'),
  (110, 2, 'KRE', 'OPS', '2026-03-01', 250000, 200000, 50000, '2026-04-01T00:00:00Z'),
  (111, 3, 'KSH', 'SEC', '2026-03-01', 200000, 160000, 40000, '2026-04-01T00:00:00Z'),
  (112, 4, 'KSH', 'SEC', '2026-03-01', 180000, 144000, 36000, '2026-04-01T00:00:00Z');
