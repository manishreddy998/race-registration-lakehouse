-- Fails if any email-looking or phone-looking value reached silver/gold.
select * from {{ ref('silver_participants') }}
where email_token like '%@%' or phone_token like '+1-%'
