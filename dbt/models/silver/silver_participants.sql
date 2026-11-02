-- PII is masked here so nothing downstream can leak it.
select participant_id,
       {{ mask_pii('email') }}                       as email_token,
       {{ mask_pii('phone') }}                       as phone_token,
       extract(year from cast(birth_date as date))   as birth_year,
       gender,
       left(postal_code, 3)                          as postal_fsa
from {{ source('bronze', 'rds_participants') }}
