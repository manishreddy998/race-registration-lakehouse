select registration_id, race_id, participant_id, price_tier_id, promo_code,
       amount, currency, status,
       cast(created_at as timestamp) as registered_at,
       cast(created_at as date)      as registered_date
from {{ source('bronze', 'rds_registrations') }}
