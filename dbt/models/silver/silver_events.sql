select event_id, event_name, city, province_state, country, currency,
       cast(race_date as date) as race_date,
       cast(registration_open as date) as registration_open,
       organizer_id, has_fundraising, platform_fee_pct
from {{ source('bronze', 'rds_events') }}
