-- =============================================================================
-- HR_MART — modélisation en étoile (Kimball) du domaine RH (ADR-0002, ADR-0008)
-- Dimensions conformes (réutilisables par d'autres marts) + faits RH + vue mart.hr_kpi.
-- NOTE : non exécuté ici (pas d'instance Postgres) ; DDL de référence à valider.
-- La sémantique des KPI fait foi côté domaine pur Python (ADR-0006) :
--   backend/src/k_insight/kpi/hr.py — ces objets SQL doivent rester cohérents avec lui.
-- =============================================================================

-- ----------------------------------------------------------------------------
-- Dimensions conformes (schéma warehouse)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key      INTEGER PRIMARY KEY,         -- AAAAMMJJ
    full_date     DATE NOT NULL UNIQUE,
    year          SMALLINT NOT NULL,
    quarter       SMALLINT NOT NULL,
    month         SMALLINT NOT NULL,
    month_name    TEXT NOT NULL,
    day           SMALLINT NOT NULL,
    is_working_day BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS warehouse.dim_subsidiary (
    subsidiary_key BIGSERIAL PRIMARY KEY,
    subsidiary_code TEXT NOT NULL UNIQUE,       -- KRE, KSH, MYK…
    subsidiary_name TEXT NOT NULL,
    entity_code    TEXT,                        -- entité juridique
    country        TEXT NOT NULL DEFAULT 'CI',
    currency       TEXT NOT NULL DEFAULT 'XOF'
);

CREATE TABLE IF NOT EXISTS warehouse.dim_department (
    department_key BIGSERIAL PRIMARY KEY,
    department_code TEXT NOT NULL,              -- OPS, SEC, FIN, RH…
    department_name TEXT NOT NULL,
    subsidiary_key BIGINT NOT NULL REFERENCES warehouse.dim_subsidiary(subsidiary_key),
    UNIQUE (subsidiary_key, department_code)
);

-- dim_employee en SCD type 2 (historisation des affectations / postes)
CREATE TABLE IF NOT EXISTS warehouse.dim_employee (
    employee_key   BIGSERIAL PRIMARY KEY,
    employee_id    TEXT NOT NULL,               -- clé naturelle source (Odoo)
    full_name      TEXT,                        -- donnée nominative : masquée selon rôle (ADR-0005)
    subsidiary_key BIGINT NOT NULL REFERENCES warehouse.dim_subsidiary(subsidiary_key),
    department_key BIGINT NOT NULL REFERENCES warehouse.dim_department(department_key),
    hired_on       DATE NOT NULL,
    terminated_on  DATE,                         -- premier jour non travaillé (convention domaine pur)
    valid_from     TIMESTAMPTZ NOT NULL,         -- SCD2
    valid_to       TIMESTAMPTZ,                  -- NULL = version courante
    is_current     BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS ix_dim_employee_natural ON warehouse.dim_employee(employee_id, is_current);

-- ----------------------------------------------------------------------------
-- Faits RH (schéma warehouse)
-- ----------------------------------------------------------------------------
-- Fait de paie : 1 ligne = 1 bulletin. Montants BIGINT XOF (0 décimale, ADR-0008).
CREATE TABLE IF NOT EXISTS warehouse.fact_payroll (
    payroll_key    BIGSERIAL PRIMARY KEY,
    date_key       INTEGER NOT NULL REFERENCES warehouse.dim_date(date_key),
    employee_key   BIGINT NOT NULL REFERENCES warehouse.dim_employee(employee_key),
    subsidiary_key BIGINT NOT NULL REFERENCES warehouse.dim_subsidiary(subsidiary_key),
    department_key BIGINT NOT NULL REFERENCES warehouse.dim_department(department_key),
    gross_xof      BIGINT NOT NULL,             -- salaire brut
    net_xof        BIGINT,                      -- salaire net
    employer_charges_xof BIGINT                 -- charges patronales
);

-- Fait d'événement d'emploi : embauches / départs (alimente entrées, sorties, turnover).
CREATE TABLE IF NOT EXISTS warehouse.fact_employment_event (
    event_key      BIGSERIAL PRIMARY KEY,
    date_key       INTEGER NOT NULL REFERENCES warehouse.dim_date(date_key),
    employee_key   BIGINT NOT NULL REFERENCES warehouse.dim_employee(employee_key),
    subsidiary_key BIGINT NOT NULL REFERENCES warehouse.dim_subsidiary(subsidiary_key),
    department_key BIGINT NOT NULL REFERENCES warehouse.dim_department(department_key),
    event_type     TEXT NOT NULL CHECK (event_type IN ('hire', 'termination'))
);

-- ----------------------------------------------------------------------------
-- mart.hr_kpi — agrégat servi à l'API (filiale × département × mois)
-- Une vue ici ; on pourra la matérialiser (TABLE) si la volumétrie l'exige (ADR-0002).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.hr_kpi AS
WITH months AS (
    SELECT DISTINCT date_trunc('month', full_date)::date AS month_start, year, month
    FROM warehouse.dim_date
),
payroll AS (
    SELECT
        date_trunc('month', d.full_date)::date AS month_start,
        s.subsidiary_code,
        dep.department_code,
        SUM(f.gross_xof)::BIGINT AS payroll_mass_xof
    FROM warehouse.fact_payroll f
    JOIN warehouse.dim_date d        ON d.date_key = f.date_key
    JOIN warehouse.dim_subsidiary s  ON s.subsidiary_key = f.subsidiary_key
    JOIN warehouse.dim_department dep ON dep.department_key = f.department_key
    GROUP BY 1, 2, 3
),
events AS (
    SELECT
        date_trunc('month', d.full_date)::date AS month_start,
        s.subsidiary_code,
        dep.department_code,
        COUNT(*) FILTER (WHERE e.event_type = 'hire')        AS entries,
        COUNT(*) FILTER (WHERE e.event_type = 'termination') AS exits
    FROM warehouse.fact_employment_event e
    JOIN warehouse.dim_date d        ON d.date_key = e.date_key
    JOIN warehouse.dim_subsidiary s  ON s.subsidiary_key = e.subsidiary_key
    JOIN warehouse.dim_department dep ON dep.department_key = e.department_key
    GROUP BY 1, 2, 3
)
SELECT
    COALESCE(p.month_start, ev.month_start)        AS month_start,
    COALESCE(p.subsidiary_code, ev.subsidiary_code) AS subsidiary_code,
    COALESCE(p.department_code, ev.department_code) AS department_code,
    COALESCE(p.payroll_mass_xof, 0)::BIGINT        AS payroll_mass_xof,
    COALESCE(ev.entries, 0)                        AS entries,
    COALESCE(ev.exits, 0)                          AS exits
FROM payroll p
FULL OUTER JOIN events ev
  ON p.month_start = ev.month_start
 AND p.subsidiary_code = ev.subsidiary_code
 AND p.department_code = ev.department_code;

COMMENT ON VIEW mart.hr_kpi IS
  'KPI RH par filiale × département × mois. Sémantique de référence : kpi/hr.py (ADR-0006).';
