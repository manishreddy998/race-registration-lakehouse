-- One row per registration with its settled money from the payments stream.
with pay as (
  select registration_id,
         sum(case when event_type = 'charge.succeeded' then amount_cents else 0 end) as gross_cents,
         sum(case when event_type = 'charge.refunded'  then amount_cents else 0 end) as refunded_cents,
         sum(case when event_type = 'charge.succeeded' then fee_cents else 0 end)    as fee_cents
  from {{ ref('silver_payment_events') }}
  group by 1
)
select r.registration_id, r.race_id, ra.event_id, r.participant_id, r.registered_at, r.registered_date,
       r.status, r.promo_code is not null as used_promo, t.tier_name, r.currency,
       coalesce(p.gross_cents, 0)    / 100.0 as gross_amount,
       coalesce(p.refunded_cents, 0) / 100.0 as refunded_amount,
       coalesce(p.fee_cents, 0)      / 100.0 as platform_fee,
       (coalesce(p.gross_cents, 0) - coalesce(p.refunded_cents, 0)) / 100.0 as net_amount,
       datediff('day', r.registered_date, e.race_date) as days_before_race
from {{ ref('silver_registrations') }} r
join {{ ref('silver_races') }} ra using (race_id)
join {{ ref('silver_events') }} e on e.event_id = ra.event_id
join {{ ref('silver_price_tiers') }} t using (price_tier_id)
left join pay p using (registration_id)
