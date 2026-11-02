-- Dynamic Data Masking: only PII_ADMIN sees raw email/phone. Same rule as dbt/macros/masking.sql.
create masking policy if not exists RACE_ROSTER.BRONZE.MASK_PII as (v string) returns string ->
  case when is_role_in_session('PII_ADMIN') then v else sha2(lower(trim(v)), 256) end;
alter table RACE_ROSTER.BRONZE.RDS_PARTICIPANTS modify column email set masking policy RACE_ROSTER.BRONZE.MASK_PII;
alter table RACE_ROSTER.BRONZE.RDS_PARTICIPANTS modify column phone set masking policy RACE_ROSTER.BRONZE.MASK_PII;

-- Data Metric Functions: the native version of src/quality.py.
alter table RACE_ROSTER.SILVER.SILVER_PAYMENT_EVENTS set data_metric_schedule = 'TRIGGER_ON_CHANGES';
alter table RACE_ROSTER.SILVER.SILVER_PAYMENT_EVENTS add data metric function SNOWFLAKE.CORE.DUPLICATE_COUNT on (webhook_event_id);
alter table RACE_ROSTER.SILVER.SILVER_PAYMENT_EVENTS add data metric function SNOWFLAKE.CORE.NULL_COUNT on (registration_id);
alter table RACE_ROSTER.GOLD.FCT_REGISTRATIONS add data metric function SNOWFLAKE.CORE.FRESHNESS on (registered_at);

-- Retention: drop raw webhook payloads after 400 days (GDPR / CCPA minimisation).
create or replace task RACE_ROSTER.BRONZE.PURGE_OLD_WEBHOOKS schedule = 'USING CRON 0 3 * * * America/Toronto'
  warehouse = LOAD_XS as
  delete from RACE_ROSTER.BRONZE.PAYMENT_WEBHOOKS where created < dateadd('day', -400, current_timestamp());
