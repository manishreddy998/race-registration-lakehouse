-- Registration dynamics: cumulative sign-ups per race per day, vs capacity.
with daily as (
  select race_id, registered_date, count(*) as regs
  from {{ ref('fct_registrations') }} where status = 'confirmed'
  group by 1, 2
)
select d.race_id, ra.event_id, e.event_name, ra.distance_name, ra.capacity, d.registered_date,
       datediff('day', d.registered_date, e.race_date) as days_before_race,
       d.regs,
       sum(d.regs) over (partition by d.race_id order by d.registered_date
                         rows between unbounded preceding and current row) as cumulative_regs,
       round(100.0 * sum(d.regs) over (partition by d.race_id order by d.registered_date
                         rows between unbounded preceding and current row) / ra.capacity, 2) as pct_of_capacity
from daily d
join {{ ref('silver_races') }} ra using (race_id)
join {{ ref('silver_events') }} e on e.event_id = ra.event_id
