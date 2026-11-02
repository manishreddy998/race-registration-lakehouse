select race_id, event_id, distance_name, distance_km, capacity
from {{ source('bronze', 'rds_races') }}
