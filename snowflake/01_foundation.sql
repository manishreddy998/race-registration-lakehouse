-- Snowflake foundation with cost discipline from day 1.
-- Small warehouses, 60s auto-suspend, separate warehouses per workload so cost is attributable.
create warehouse if not exists LOAD_XS      warehouse_size = XSMALL auto_suspend = 60 auto_resume = true initially_suspended = true;
create warehouse if not exists TRANSFORM_XS warehouse_size = XSMALL auto_suspend = 60 auto_resume = true initially_suspended = true;
create warehouse if not exists BI_XS        warehouse_size = XSMALL auto_suspend = 60 auto_resume = true initially_suspended = true
  max_cluster_count = 2 scaling_policy = ECONOMY;

create resource monitor if not exists RR_MONTHLY with credit_quota = 200 frequency = MONTHLY start_timestamp = IMMEDIATELY
  triggers on 80 percent do notify on 100 percent do suspend;
alter warehouse TRANSFORM_XS set resource_monitor = RR_MONTHLY;

create database if not exists RACE_ROSTER;
create schema if not exists RACE_ROSTER.BRONZE data_retention_time_in_days = 7;
create schema if not exists RACE_ROSTER.SILVER data_retention_time_in_days = 1;
create schema if not exists RACE_ROSTER.GOLD   data_retention_time_in_days = 1;

create role if not exists LOADER; create role if not exists TRANSFORMER;
create role if not exists ANALYST; create role if not exists PII_ADMIN;
grant usage on schema RACE_ROSTER.GOLD to role ANALYST;           -- Metabase only sees gold
grant select on future tables in schema RACE_ROSTER.GOLD to role ANALYST;
grant select on future dynamic tables in schema RACE_ROSTER.GOLD to role ANALYST;
