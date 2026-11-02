select * from {{ ref('fct_registrations') }} where refunded_amount > gross_amount
