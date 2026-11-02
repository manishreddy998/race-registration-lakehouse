select date_trunc('month', registered_date) as revenue_month, currency,
       count(*) filter (where status = 'confirmed') as registrations,
       sum(gross_amount)    as gross_revenue,
       sum(refunded_amount) as refunds,
       sum(net_amount)      as net_revenue,
       sum(platform_fee)    as platform_fees
from {{ ref('fct_registrations') }}
group by 1, 2
