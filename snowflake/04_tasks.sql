-- Snowflake-native serverless orchestration (Tasks) instead of an external scheduler.
create or replace task RACE_ROSTER.GOLD.RECONCILE_REVENUE
  schedule = 'USING CRON 15 * * * * America/Toronto'
  user_task_managed_initial_warehouse_size = 'XSMALL' as
  insert into RACE_ROSTER.GOLD.RECONCILIATION_LOG
  select current_timestamp(), g.event_id, g.net_cents, s.net_cents, g.net_cents = s.net_cents
  from (select event_id, sum(net_amount) * 100 net_cents from RACE_ROSTER.GOLD.FCT_REGISTRATIONS group by 1) g
  full outer join (
    select ra.event_id, sum(iff(p.event_type = 'charge.succeeded', 1, -1) * p.amount_cents) net_cents
    from RACE_ROSTER.SILVER.SILVER_PAYMENT_EVENTS p
    join RACE_ROSTER.BRONZE.RDS_REGISTRATIONS r using (registration_id)
    join RACE_ROSTER.BRONZE.RDS_RACES ra using (race_id) group by 1) s using (event_id);
alter task RACE_ROSTER.GOLD.RECONCILE_REVENUE resume;

-- FinOps: daily cost per warehouse, for a Metabase cost dashboard.
create or replace view RACE_ROSTER.GOLD.FINOPS_DAILY_CREDITS as
select date_trunc('day', start_time) as usage_day, warehouse_name, sum(credits_used) as credits
from SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY group by 1, 2;
