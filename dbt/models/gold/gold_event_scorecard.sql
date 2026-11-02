with regs as (
  select event_id, count(*) filter (where status = 'confirmed') as participants,
         sum(net_amount) as net_revenue, sum(platform_fee) as platform_fees,
         count(distinct participant_id) as unique_runners
  from {{ ref('fct_registrations') }} group by 1
), cap as (
  select event_id, sum(capacity) as capacity from {{ ref('silver_races') }} group by 1
), fund as (
  select event_id, sum(amount) as funds_raised, count(distinct fundraising_page_id) as fundraising_pages
  from {{ ref('silver_donations') }} group by 1
), first_seen as (
  select participant_id, min(registered_at) as first_registered_at
  from {{ ref('fct_registrations') }} group by 1
), repeat_runners as (
  select f.event_id, count(distinct f.participant_id) as returning_runners
  from {{ ref('fct_registrations') }} f join first_seen s using (participant_id)
  where f.registered_at > s.first_registered_at
  group by 1
)
select e.event_id, e.event_name, e.city, e.country, e.currency, e.race_date,
       r.participants, c.capacity, round(100.0 * r.participants / c.capacity, 1) as fill_rate_pct,
       round(r.net_revenue, 2) as net_revenue, round(r.platform_fees, 2) as platform_fees,
       coalesce(f.funds_raised, 0) as funds_raised, coalesce(f.fundraising_pages, 0) as fundraising_pages,
       round(100.0 * coalesce(rt.returning_runners, 0) / r.unique_runners, 1) as returning_runner_pct
from {{ ref('silver_events') }} e
join regs r using (event_id) join cap c using (event_id)
left join fund f using (event_id) left join repeat_runners rt using (event_id)
