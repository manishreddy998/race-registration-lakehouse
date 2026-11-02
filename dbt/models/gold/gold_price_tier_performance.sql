select ra.distance_name, f.tier_name, f.currency,
       count(*)                          as registrations,
       round(avg(f.gross_amount), 2)     as avg_paid,
       round(100.0 * avg(case when f.used_promo then 1 else 0 end), 1) as promo_share_pct,
       round(sum(f.net_amount), 2)       as net_revenue
from {{ ref('fct_registrations') }} f
join {{ ref('silver_races') }} ra using (race_id)
where f.status = 'confirmed'
group by 1, 2, 3
