-- Staging RH : nettoyage / typage / renommage des employés Odoo (ADR-0003).
-- Aucune logique de KPI ici — uniquement la mise en forme.

with source as (
    select * from {{ source('raw', 'odoo_hr_employee') }}
),

renamed as (
    select
        id::text                                as employee_id,
        nullif(trim(name), '')                  as full_name,
        upper(trim(subsidiary_code))            as subsidiary_code,
        upper(trim(department_code))            as department_code,
        date_hired::date                        as hired_on,
        -- Convention domaine pur : terminated_on = premier jour NON travaillé.
        date_departure::date                    as terminated_on,
        _airbyte_extracted_at                   as extracted_at
    from source
)

select * from renamed
