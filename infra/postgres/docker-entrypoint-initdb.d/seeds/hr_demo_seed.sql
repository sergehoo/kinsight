-- =============================================================================
-- Seed de démonstration HR_MART — reproduit EXACTEMENT le jeu de test vérifié
-- du domaine pur (backend/tests/test_hr_kpis.py).
-- Après application, mart.hr_kpi doit donner pour Q1 2026 :
--   masse salariale totale = 3 110 000 XOF (KRE 2 150 000, KSH 960 000)
--   entrées Q1 = 1 (E4), sorties Q1 = 2 (E2, E5)
-- Usage : psql -d k_insight_edw -f warehouse/ddl/seeds/hr_demo_seed.sql
-- =============================================================================

TRUNCATE warehouse.fact_payroll, warehouse.fact_employment_event,
         warehouse.dim_employee, warehouse.dim_department,
         warehouse.dim_subsidiary, warehouse.dim_date RESTART IDENTITY CASCADE;

-- dim_date : 2023 → 2026 (couvre embauches anciennes + période d'analyse)
INSERT INTO warehouse.dim_date (date_key, full_date, year, quarter, month, month_name, day, is_working_day)
SELECT to_char(d, 'YYYYMMDD')::int, d::date,
       extract(year from d)::smallint, extract(quarter from d)::smallint,
       extract(month from d)::smallint, trim(to_char(d, 'Month')),
       extract(day from d)::smallint, extract(isodow from d) < 6
FROM generate_series('2023-01-01'::date, '2026-12-31'::date, '1 day') AS g(d);

-- Filiales
INSERT INTO warehouse.dim_subsidiary (subsidiary_code, subsidiary_name) VALUES
  ('KRE', 'K-Express'),
  ('KSH', 'K-Shield'),
  ('MYK', 'MyKaydan');

-- Départements (par filiale)
INSERT INTO warehouse.dim_department (department_code, department_name, subsidiary_key)
SELECT v.code, v.name, s.subsidiary_key
FROM (VALUES ('OPS', 'Opérations', 'KRE'),
             ('FIN', 'Finance', 'KRE'),
             ('SEC', 'Sécurité', 'KSH')) AS v(code, name, subcode)
JOIN warehouse.dim_subsidiary s ON s.subsidiary_code = v.subcode;

-- Employés (E1..E5)
INSERT INTO warehouse.dim_employee
  (employee_id, full_name, subsidiary_key, department_key, hired_on, terminated_on, valid_from, is_current)
SELECT v.emp, v.fname, s.subsidiary_key, dep.department_key, v.hired, v.term,
       '2023-01-01'::timestamptz, true
FROM (VALUES
  ('E1', 'Awa Koné',      'KRE', 'OPS', '2025-01-01'::date, NULL::date),
  ('E2', 'Bakary Touré',  'KRE', 'OPS', '2025-06-01',       '2026-03-15'),
  ('E3', 'Cica Yao',      'KSH', 'SEC', '2024-03-01',       NULL),
  ('E4', 'Daouda Bamba',  'KSH', 'SEC', '2026-02-01',       NULL),
  ('E5', 'Esther Diallo', 'KRE', 'FIN', '2023-01-01',       '2026-01-10')
) AS v(emp, fname, subcode, depcode, hired, term)
JOIN warehouse.dim_subsidiary s ON s.subsidiary_code = v.subcode
JOIN warehouse.dim_department dep
  ON dep.department_code = v.depcode AND dep.subsidiary_key = s.subsidiary_key;

-- Bulletins de paie (Q1 2026)
INSERT INTO warehouse.fact_payroll (date_key, employee_key, subsidiary_key, department_key, gross_xof)
SELECT d.date_key, e.employee_key, e.subsidiary_key, e.department_key, v.gross
FROM (VALUES
  ('E1', '2026-01-01'::date, 300000), ('E2', '2026-01-01', 250000),
  ('E3', '2026-01-01', 200000),       ('E5', '2026-01-01', 500000),
  ('E1', '2026-02-01', 300000),       ('E2', '2026-02-01', 250000),
  ('E3', '2026-02-01', 200000),       ('E4', '2026-02-01', 180000),
  ('E1', '2026-03-01', 300000),       ('E2', '2026-03-01', 250000),
  ('E3', '2026-03-01', 200000),       ('E4', '2026-03-01', 180000)
) AS v(emp, pay_date, gross)
JOIN warehouse.dim_date d ON d.full_date = v.pay_date
JOIN warehouse.dim_employee e ON e.employee_id = v.emp;

-- Événements d'emploi (embauches + départs)
INSERT INTO warehouse.fact_employment_event (date_key, employee_key, subsidiary_key, department_key, event_type)
SELECT d.date_key, e.employee_key, e.subsidiary_key, e.department_key, v.etype
FROM (VALUES
  ('E1', '2025-01-01'::date, 'hire'), ('E2', '2025-06-01', 'hire'),
  ('E3', '2024-03-01', 'hire'),       ('E4', '2026-02-01', 'hire'),
  ('E5', '2023-01-01', 'hire'),
  ('E2', '2026-03-15', 'termination'),('E5', '2026-01-10', 'termination')
) AS v(emp, edate, etype)
JOIN warehouse.dim_date d ON d.full_date = v.edate
JOIN warehouse.dim_employee e ON e.employee_id = v.emp;
