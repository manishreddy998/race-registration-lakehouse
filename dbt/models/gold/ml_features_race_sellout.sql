-- Feature table for an AI use case: predict final registrations for a race
-- using only what is known halfway through its registration window.
with win as (
  select ra.race_id, ra.event_id, ra.distance_name, ra.capacity, e.registration_open, e.race_date,
         e.country, e.has_fundraising,
         datediff('day', e.registration_open, e.race_date) as window_days
  from {{ ref('silver_races') }} ra join {{ ref('silver_events') }} e using (event_id)
), agg as (
  select w.race_id,
         count(*) filter (where f.registered_date < w.registration_open + cast(w.window_days / 2 as integer)) as regs_at_midpoint,
         count(*) filter (where f.registered_date < w.registration_open + cast(w.window_days / 4 as integer)) as regs_at_quarter,
         count(*) filter (where f.tier_name = 'Early Bird') as early_bird_regs,
         count(*) as final_regs
  from win w left join {{ ref('fct_registrations') }} f
    on f.race_id = w.race_id and f.status = 'confirmed'
  group by 1
)
select w.*, a.regs_at_quarter, a.regs_at_midpoint, a.early_bird_regs, a.final_regs,
       round(1.0 * a.regs_at_midpoint / w.capacity, 4) as midpoint_fill
from win w join agg a using (race_id)
