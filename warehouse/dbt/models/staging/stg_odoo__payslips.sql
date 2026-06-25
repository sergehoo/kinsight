-- Staging RH : bulletins de paie Odoo. Montants ramenés en XOF entiers (ADR-0008).

with source as (
    select * from {{ source('raw', 'odoo_hr_payslip') }}
),

renamed as (
    select
        id::text                                as payslip_id,
        employee_id::text                       as employee_id,
        upper(trim(subsidiary_code))            as subsidiary_code,
        upper(trim(department_code))            as department_code,
        date_from::date                         as pay_date,
        round(gross_amount)::bigint             as gross_xof,
        round(net_amount)::bigint               as net_xof,
        round(employer_charges)::bigint         as employer_charges_xof
    from source
)

select * from renamed
