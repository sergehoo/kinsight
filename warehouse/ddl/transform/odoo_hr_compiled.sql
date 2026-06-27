-- =============================================================================
-- Transformation Odoo RH — ÉQUIVALENT SQL des modèles dbt (raw → staging → mart).
-- Source de vérité = les modèles dbt (warehouse/dbt/models/...). Ce fichier en est la
-- compilation manuelle, pour : (1) valider la chaîne sans le CLI dbt, (2) servir de
-- référence. `dbt build` reste la voie de production (matérialise staging=views, mart=table).
-- Cohérent avec la sémantique du domaine pur kpi/hr.py (ADR-0006).
-- =============================================================================

-- Staging : nettoyage / typage (mirror de stg_odoo__employees.sql).
CREATE OR REPLACE VIEW staging.stg_odoo__employees AS
SELECT
    id::text                     AS employee_id,
    nullif(trim(name), '')       AS full_name,
    upper(trim(subsidiary_code)) AS subsidiary_code,
    upper(trim(department_code)) AS department_code,
    date_hired::date             AS hired_on,
    date_departure::date         AS terminated_on,
    _airbyte_extracted_at        AS extracted_at
FROM raw.odoo_hr_employee;

CREATE OR REPLACE VIEW staging.stg_odoo__payslips AS
SELECT
    id::text                     AS payslip_id,
    employee_id::text            AS employee_id,
    upper(trim(subsidiary_code)) AS subsidiary_code,
    upper(trim(department_code)) AS department_code,
    date_from::date              AS pay_date,
    round(gross_amount)::bigint  AS gross_xof,
    round(net_amount)::bigint    AS net_xof,
    round(employer_charges)::bigint AS employer_charges_xof
FROM raw.odoo_hr_payslip;

-- Mart RH (mirror de marts/hr/hr_kpi.sql). En prod dbt le matérialise en TABLE `mart.hr_kpi`.
CREATE OR REPLACE VIEW mart.hr_kpi AS
WITH payroll AS (
    SELECT date_trunc('month', pay_date)::date AS month_start, subsidiary_code, department_code,
           sum(gross_xof)::bigint AS payroll_mass_xof
    FROM staging.stg_odoo__payslips GROUP BY 1, 2, 3
),
entries AS (
    SELECT date_trunc('month', hired_on)::date AS month_start, subsidiary_code, department_code,
           count(*) AS entries
    FROM staging.stg_odoo__employees GROUP BY 1, 2, 3
),
exits AS (
    SELECT date_trunc('month', terminated_on)::date AS month_start, subsidiary_code, department_code,
           count(*) AS exits
    FROM staging.stg_odoo__employees WHERE terminated_on IS NOT NULL GROUP BY 1, 2, 3
)
SELECT
    coalesce(p.month_start, en.month_start, ex.month_start)              AS month_start,
    coalesce(p.subsidiary_code, en.subsidiary_code, ex.subsidiary_code)  AS subsidiary_code,
    coalesce(p.department_code, en.department_code, ex.department_code)  AS department_code,
    coalesce(p.payroll_mass_xof, 0)::bigint                              AS payroll_mass_xof,
    coalesce(en.entries, 0)                                             AS entries,
    coalesce(ex.exits, 0)                                               AS exits
FROM payroll p
FULL OUTER JOIN entries en USING (month_start, subsidiary_code, department_code)
FULL OUTER JOIN exits ex   USING (month_start, subsidiary_code, department_code);
