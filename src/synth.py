"""Generate realistic synthetic Race Roster-style source data.

Two kinds of sources, matching the job post:
1. An AWS RDS (Postgres) style OLTP snapshot: events, races, price tiers,
   participants, registrations, fundraising pages and donations.
2. A payments webhook stream (JSON lines), like a payment processor posts:
   charge.succeeded, charge.refunded, payout.paid. It includes real-world
   mess on purpose: duplicate deliveries, out-of-order and late events.

Everything is seeded so every run produces the same numbers.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

SEED = 2011  # Race Roster was founded in London, ON in 2011
OUT = Path("data/source")

CITIES = [
    ("London", "ON", "CA", "CAD"), ("Toronto", "ON", "CA", "CAD"), ("Ottawa", "ON", "CA", "CAD"),
    ("Hamilton", "ON", "CA", "CAD"), ("Halifax", "NS", "CA", "CAD"), ("Calgary", "AB", "CA", "CAD"),
    ("Vancouver", "BC", "CA", "CAD"), ("Montreal", "QC", "CA", "CAD"), ("Winnipeg", "MB", "CA", "CAD"),
    ("Boston", "MA", "US", "USD"), ("Chicago", "IL", "US", "USD"), ("Denver", "CO", "US", "USD"),
    ("Austin", "TX", "US", "USD"), ("Portland", "OR", "US", "USD"), ("Buffalo", "NY", "US", "USD"),
]
EVENT_KINDS = ["Marathon Weekend", "Half Marathon", "Spring 10K", "Turkey Trot", "Charity 5K",
               "Trail Run", "Run for the Cure", "Harbour Run", "Island Race", "Valley Ultra"]
DISTANCES = {  # name, km, base price
    "5K": (5.0, 45), "10K": (10.0, 60), "Half Marathon": (21.1, 95),
    "Marathon": (42.2, 140), "Kids 1K": (1.0, 15), "50K Ultra": (50.0, 165),
}
TIERS = [("Early Bird", 0.80), ("Regular", 1.00), ("Late", 1.20)]
FIRST = ["Olivia", "Liam", "Emma", "Noah", "Ava", "Lucas", "Mia", "Ethan", "Sofia", "Aarav",
         "Priya", "Wei", "Chloe", "Mateo", "Zoe", "Arjun", "Hannah", "Omar", "Isla", "Kai"]
LAST = ["Smith", "Brown", "Tremblay", "Martin", "Roy", "Wilson", "Patel", "Singh", "Nguyen",
        "Chen", "Lee", "Gagnon", "Taylor", "Campbell", "Anderson", "Reddy", "Khan", "Murphy"]


def _sigmoid_curve(rng: random.Random, n: int, open_d: date, close_d: date) -> list[date]:
    """Registrations bunch up near tier price jumps and race day, like real races."""
    span = (close_d - open_d).days
    out = []
    for _ in range(n):
        u = rng.random()
        # mix: steady trickle, early-bird spike, final-weeks surge
        if u < 0.25:
            d = rng.betavariate(1.2, 4) * span
        elif u < 0.55:
            d = rng.uniform(0, span)
        else:
            d = rng.betavariate(5, 1.4) * span
        out.append(open_d + timedelta(days=int(d)))
    return out


def generate(n_events: int = 60, out: Path = OUT) -> dict:
    rng = random.Random(SEED)
    out.mkdir(parents=True, exist_ok=True)
    events, races, tiers, participants, regs, pages, donations = [], [], [], [], [], [], []
    webhooks = []
    pid = rid = tid = regid = pgid = did = 0
    participant_pool: list[int] = []

    for e in range(1, n_events + 1):
        city, prov, country, cur = rng.choice(CITIES)
        kind = rng.choice(EVENT_KINDS)
        race_day = date(2025, 3, 1) + timedelta(days=rng.randint(0, 600))
        open_d = race_day - timedelta(days=rng.randint(120, 240))
        charity = rng.random() < 0.45
        events.append(dict(event_id=e, event_name=f"{city} {kind} {race_day.year}", city=city,
                           province_state=prov, country=country, currency=cur,
                           race_date=race_day.isoformat(), registration_open=open_d.isoformat(),
                           organizer_id=100 + rng.randint(1, 25), has_fundraising=charity,
                           platform_fee_pct=round(rng.choice([0.05, 0.06, 0.065]), 3)))
        dist_names = rng.sample(list(DISTANCES), k=rng.randint(2, 4))
        for dn in dist_names:
            rid += 1
            km, base = DISTANCES[dn]
            cap = rng.choice([150, 250, 400, 600, 1000, 1500])
            races.append(dict(race_id=rid, event_id=e, distance_name=dn, distance_km=km, capacity=cap))
            span = (race_day - open_d).days
            cut1 = open_d + timedelta(days=int(span * 0.35))
            cut2 = open_d + timedelta(days=int(span * 0.85))
            bounds = [(open_d, cut1), (cut1, cut2), (cut2, race_day)]
            tier_ids = []
            for (tn, mult), (a, b) in zip(TIERS, bounds):
                tid += 1
                tier_ids.append((tid, a, b, round(base * mult, 2)))
                tiers.append(dict(price_tier_id=tid, race_id=rid, tier_name=tn,
                                  price=round(base * mult, 2), valid_from=a.isoformat(),
                                  valid_to=b.isoformat()))
            demand = rng.uniform(0.45, 1.15)
            n = min(cap, int(cap * demand))
            for d in sorted(_sigmoid_curve(rng, n, open_d, race_day - timedelta(days=1))):
                if participant_pool and rng.random() < 0.3:
                    p = rng.choice(participant_pool)  # returning runner
                else:
                    pid += 1
                    p = pid
                    participant_pool.append(p)
                    fn, ln = rng.choice(FIRST), rng.choice(LAST)
                    participants.append(dict(
                        participant_id=p, first_name=fn, last_name=ln,
                        email=f"{fn.lower()}.{ln.lower()}{p}@example.com",
                        phone=f"+1-519-555-{p % 10000:04d}",
                        birth_date=(date(1960, 1, 1) + timedelta(days=rng.randint(0, 20000))).isoformat(),
                        gender=rng.choice(["F", "M", "X"]), postal_code=f"N6A {rng.randint(1,9)}B{rng.randint(1,9)}"))
                t = next(t for t in tier_ids if t[1] <= d < t[2] or t is tier_ids[-1])
                regid += 1
                promo = rng.random() < 0.12
                amount = round(t[3] * (0.85 if promo else 1.0), 2)
                ts = datetime.combine(d, datetime.min.time()) + timedelta(minutes=rng.randint(0, 1439))
                status = "cancelled" if rng.random() < 0.03 else "confirmed"
                regs.append(dict(registration_id=regid, race_id=rid, participant_id=p,
                                 price_tier_id=t[0], promo_code="RUNCLUB15" if promo else None,
                                 amount=amount, currency=cur, status=status,
                                 created_at=ts.isoformat(), updated_at=ts.isoformat()))
                fee = round(amount * events[-1]["platform_fee_pct"], 2)
                charge = f"ch_{regid:07d}"
                ev = dict(id=f"evt_c{regid:07d}", type="charge.succeeded", created=ts.isoformat(),
                          data=dict(charge_id=charge, registration_id=regid, amount_cents=int(round(amount*100)),
                                    fee_cents=int(round(fee*100)), currency=cur.lower()))
                webhooks.append(ev)
                if rng.random() < 0.04:  # processor retried delivery -> duplicate
                    webhooks.append(dict(ev))
                if status == "cancelled" or rng.random() < 0.02:
                    rts = ts + timedelta(days=rng.randint(1, 20))
                    webhooks.append(dict(id=f"evt_r{regid:07d}", type="charge.refunded", created=rts.isoformat(),
                                         data=dict(charge_id=charge, registration_id=regid,
                                                   amount_cents=int(round(amount*100)), fee_cents=0,
                                                   currency=cur.lower())))
        if charity:
            for _ in range(rng.randint(5, 25)):
                pgid += 1
                goal = rng.choice([250, 500, 1000, 2500])
                pages.append(dict(fundraising_page_id=pgid, event_id=e,
                                  participant_id=rng.choice(participant_pool), goal_amount=goal,
                                  charity_name=rng.choice(["Canadian Cancer Society", "Heart & Stroke",
                                                           "Local Food Bank", "Children's Hospital Foundation"])))
                for _ in range(rng.randint(0, 18)):
                    did += 1
                    dts = datetime.combine(race_day, datetime.min.time()) - timedelta(days=rng.randint(0, 90))
                    donations.append(dict(donation_id=did, fundraising_page_id=pgid,
                                          amount=float(rng.choice([10, 20, 25, 50, 100, 250])),
                                          currency=cur, donated_at=dts.isoformat(),
                                          donor_email=f"donor{did}@example.org"))

    # webhooks arrive out of order (network) -> shuffle 10% of positions
    for _ in range(len(webhooks) // 10):
        i, j = rng.randrange(len(webhooks)), rng.randrange(len(webhooks))
        webhooks[i], webhooks[j] = webhooks[j], webhooks[i]

    tables = dict(events=events, races=races, price_tiers=tiers, participants=participants,
                  registrations=regs, fundraising_pages=pages, donations=donations)
    rds = out / "rds"
    rds.mkdir(exist_ok=True)
    for name, rows in tables.items():
        pd.DataFrame(rows).to_parquet(rds / f"{name}.parquet", index=False)
    with open(out / "payment_webhooks.jsonl", "w") as f:
        for w in webhooks:
            f.write(json.dumps(w) + "\n")
    stats = {k: len(v) for k, v in tables.items()}
    stats["payment_webhooks"] = len(webhooks)
    stats["duplicate_webhook_deliveries"] = len(webhooks) - len({w["id"] for w in webhooks})
    return stats


if __name__ == "__main__":
    s = generate()
    Path("results").mkdir(exist_ok=True)
    Path("results/source_stats.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s, indent=2))
