-- A registration can only be charged its tier price, or tier price minus the 15% promo.
select f.registration_id from {{ ref('fct_registrations') }} f
join {{ ref('silver_registrations') }} r using (registration_id)
join {{ ref('silver_price_tiers') }} t using (price_tier_id)
where abs(f.gross_amount - t.price) > 0.01 and abs(f.gross_amount - round(t.price * 0.85, 2)) > 0.01
