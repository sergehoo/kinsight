-- Test singulier dbt : réconciliation mart.hr_kpi ↔ staging (aucune perte dans les jointures).
-- Un test singulier ÉCHOUE s'il renvoie ≥ 1 ligne. On vérifie trois invariants :
--   1) masse salariale agrégée = somme des bulletins ;
--   2) total entrées = nombre d'employés (chaque employé a une date d'embauche) ;
--   3) total sorties = nombre d'employés avec date de départ.
-- Garantit que la transformation raw→mart ne perd ni ne double aucune donnée (ADR-0006).

with kpi as (select * from {{ ref('hr_kpi') }}),
emp as (select * from {{ ref('stg_odoo__employees') }}),
pay as (select * from {{ ref('stg_odoo__payslips') }}),

checks as (
    select 'masse_salariale' as invariant,
           (select coalesce(sum(payroll_mass_xof), 0) from kpi) as mart_value,
           (select coalesce(sum(gross_xof), 0) from pay)        as expected
    union all
    select 'entrees',
           (select coalesce(sum(entries), 0) from kpi),
           (select count(*) from emp)
    union all
    select 'sorties',
           (select coalesce(sum(exits), 0) from kpi),
           (select count(*) from emp where terminated_on is not null)
)

select * from checks where mart_value <> expected
