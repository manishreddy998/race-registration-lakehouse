select price_tier_id, race_id, tier_name, price,
       cast(valid_from as date) as valid_from, cast(valid_to as date) as valid_to
from {{ source('bronze', 'rds_price_tiers') }}
