select d.donation_id, d.fundraising_page_id, p.event_id, p.participant_id, p.charity_name,
       p.goal_amount, d.amount, d.currency, cast(d.donated_at as timestamp) as donated_at
from {{ source('bronze', 'rds_donations') }} d
join {{ source('bronze', 'rds_fundraising_pages') }} p using (fundraising_page_id)
