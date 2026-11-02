-- Bronze -> silver -> gold as small, focused Dynamic Tables.
-- Same logic as dbt/models; Snowflake handles incremental refresh and ordering.
create or replace dynamic table RACE_ROSTER.SILVER.SILVER_PAYMENT_EVENTS
  target_lag = '5 minutes' warehouse = TRANSFORM_XS refresh_mode = INCREMENTAL as
select id as webhook_event_id, type as event_type, created::timestamp_ntz as event_at,
       data__charge_id as charge_id, data__registration_id as registration_id,
       data__amount_cents as amount_cents, data__fee_cents as fee_cents, upper(data__currency) as currency
from RACE_ROSTER.BRONZE.PAYMENT_WEBHOOKS
qualify row_number() over (partition by id order by _dlt_load_id, _dlt_id) = 1;

create or replace dynamic table RACE_ROSTER.GOLD.FCT_REGISTRATIONS
  target_lag = 'DOWNSTREAM' warehouse = TRANSFORM_XS as
with pay as (
  select registration_id,
         sum(iff(event_type = 'charge.succeeded', amount_cents, 0)) as gross_cents,
         sum(iff(event_type = 'charge.refunded',  amount_cents, 0)) as refunded_cents,
         sum(iff(event_type = 'charge.succeeded', fee_cents, 0))    as fee_cents
  from RACE_ROSTER.SILVER.SILVER_PAYMENT_EVENTS group by 1)
select r.registration_id, r.race_id, ra.event_id, r.participant_id, r.created_at::timestamp_ntz as registered_at,
       r.status, t.tier_name, r.currency,
       coalesce(p.gross_cents, 0) / 100 as gross_amount, coalesce(p.refunded_cents, 0) / 100 as refunded_amount,
       (coalesce(p.gross_cents, 0) - coalesce(p.refunded_cents, 0)) / 100 as net_amount
from RACE_ROSTER.BRONZE.RDS_REGISTRATIONS r
join RACE_ROSTER.BRONZE.RDS_RACES ra using (race_id)
join RACE_ROSTER.BRONZE.RDS_PRICE_TIERS t using (price_tier_id)
left join pay p using (registration_id);

create or replace dynamic table RACE_ROSTER.GOLD.GOLD_REVENUE_MONTHLY
  target_lag = '1 hour' warehouse = TRANSFORM_XS as
select date_trunc('month', registered_at) as revenue_month, currency,
       count_if(status = 'confirmed') as registrations, sum(net_amount) as net_revenue
from RACE_ROSTER.GOLD.FCT_REGISTRATIONS group by 1, 2;
