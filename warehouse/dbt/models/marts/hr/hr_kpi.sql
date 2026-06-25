-- mart.hr_kpi (dbt) — agrégat RH par filiale × département × mois.
-- Doit rester cohérent avec la sémantique de référence kpi/hr.py (ADR-0006).
-- Test de réconciliation à ajouter : comparer un échantillon à la sortie du domaine pur.

with payslips as (
    select * from {{ ref('stg_odoo__payslips') }}
),

payroll as (
    select
        date_trunc('month', pay_date)::date as month_start,
        subsidiary_code,
        department_code,
        sum(gross_xof)::bigint              as payroll_mass_xof
    from payslips
    group by 1, 2, 3
),

employees as (
    select * from {{ ref('stg_odoo__employees') }}
),

entries as (
    select
        date_trunc('month', hired_on)::date as month_start,
        subsidiary_code,
        department_code,
        count(*)                            as entries
    from employees
    group by 1, 2, 3
),

exits as (
    select
        date_trunc('month', terminated_on)::date as month_start,
        subsidiary_code,
        department_code,
        count(*)                                 as exits
    from employees
    where terminated_on is not null
    group by 1, 2, 3
)

select
    coalesce(p.month_start, en.month_start, ex.month_start)          as month_start,
    coalesce(p.subsidiary_code, en.subsidiary_code, ex.subsidiary_code) as subsidiary_code,
    coalesce(p.department_code, en.department_code, ex.department_code) as department_code,
    coalesce(p.payroll_mass_xof, 0)::bigint                          as payroll_mass_xof,
    coalesce(en.entries, 0)                                          as entries,
    coalesce(ex.exits, 0)                                            as exits
from payroll p
full outer join entries en using (month_start, subsidiary_code, department_code)
full outer join exits ex   using (month_start, subsidiary_code, department_code)
