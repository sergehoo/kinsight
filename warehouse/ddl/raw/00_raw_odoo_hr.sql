-- =============================================================================
-- CONTRAT RAW — Odoo RH (ce qu'Airbyte doit produire dans le schéma `raw`, ADR-0003).
-- Airbyte copie les sources TELLES QUELLES ; ces tables matérialisent le contrat de colonnes
-- attendu par les modèles dbt de staging (stg_odoo__employees / stg_odoo__payslips).
-- En production, Airbyte CRÉE ces tables ; ce DDL sert de référence + base de test local.
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw.odoo_hr_employee (
    id                    BIGINT,          -- clé naturelle Odoo (hr.employee)
    name                  TEXT,
    subsidiary_code       TEXT,            -- KRE / KSH / MYK
    department_code       TEXT,            -- OPS / SEC / FIN…
    date_hired            DATE,
    date_departure        DATE,            -- premier jour NON travaillé (NULL = en poste)
    _airbyte_extracted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS raw.odoo_hr_payslip (
    id                    BIGINT,          -- clé naturelle Odoo (hr.payslip)
    employee_id           BIGINT,
    subsidiary_code       TEXT,
    department_code       TEXT,
    date_from             DATE,            -- début de période de paie
    gross_amount          NUMERIC,         -- brut (converti en XOF entier par le staging)
    net_amount            NUMERIC,
    employer_charges      NUMERIC,
    _airbyte_extracted_at TIMESTAMPTZ
);
