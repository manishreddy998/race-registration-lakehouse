-- Webhooks can be delivered more than once and out of order.
-- Keep exactly one row per event id (first delivery wins).
with ranked as (
  select id as webhook_event_id, type as event_type, cast(created as timestamp) as event_at,
         data__charge_id as charge_id, data__registration_id as registration_id,
         data__amount_cents as amount_cents, data__fee_cents as fee_cents,
         upper(data__currency) as currency, _dlt_load_id,
         row_number() over (partition by id order by _dlt_load_id, _dlt_id) as rn
  from {{ source('bronze', 'payment_webhooks') }}
)
select * exclude (rn) from ranked where rn = 1
