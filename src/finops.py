"""FinOps benchmark: what does querying the curated gold layer save
versus letting Metabase hit raw bronze directly?

We run the same 4 dashboard questions two ways and measure, from the real run:
- wall time (median of 5 runs)
- rows the engine had to read (from DuckDB's profiler)
In Snowflake, scanned data and warehouse time are what you pay credits for,
so fewer rows read and less time is the cost lever.
"""
from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

import duckdb

DB = os.environ.get("DUCKDB_PATH", "data/race_roster.duckdb")

RAW_NET = """
with d as (select *, row_number() over (partition by id order by _dlt_load_id) rn from bronze.payment_webhooks),
p as (select data__registration_id rid,
        sum(case when type='charge.succeeded' then data__amount_cents else -data__amount_cents end) c
      from d where rn = 1 group by 1)
select r.registration_id, r.race_id, ra.event_id, r.status, cast(r.created_at as date) dt, r.currency,
       r.price_tier_id, coalesce(p.c,0)/100.0 net
from bronze.rds_registrations r join bronze.rds_races ra using (race_id) left join p on p.rid = r.registration_id
"""
QUESTIONS = {
    "net_revenue_by_month": (
        f"with f as ({RAW_NET}) select date_trunc('month', dt) m, currency, sum(net) from f group by 1,2",
        "select revenue_month, currency, net_revenue from gold.gold_revenue_monthly"),
    "event_fill_rate": (
        f"with f as ({RAW_NET}) select f.event_id, count(*) filter (where status='confirmed') from f group by 1",
        "select event_id, fill_rate_pct from gold.gold_event_scorecard"),
    "tier_performance": (
        f"with f as ({RAW_NET}) select t.tier_name, count(*), sum(net) from f join bronze.rds_price_tiers t using (price_tier_id) group by 1",
        "select tier_name, registrations, net_revenue from gold.gold_price_tier_performance"),
    "pace_one_race": (
        f"with f as ({RAW_NET}) select dt, count(*) from f where race_id = 42 and status='confirmed' group by 1 order by 1",
        "select registered_date, cumulative_regs from gold.gold_registration_pace where race_id = 42"),
}


def _measure(con, sql: str) -> tuple[float, int]:
    times = []
    for _ in range(5):
        t0 = time.perf_counter(); con.execute(sql).fetchall(); times.append(time.perf_counter() - t0)
    con.execute("pragma enable_profiling='json'")
    prof = Path("data/_profile.json"); con.execute(f"pragma profiling_output='{prof}'")
    con.execute(sql).fetchall()
    con.execute("pragma disable_profiling")
    tree = json.loads(prof.read_text())

    def scanned(node):
        n = 0
        if "SCAN" in str(node.get("operator_type", node.get("operator_name", ""))).upper():
            n += int(node.get("operator_cardinality", 0) or 0)
        return n + sum(scanned(c) for c in node.get("children", []))
    return statistics.median(times) * 1000, scanned(tree)


def run() -> dict:
    con = duckdb.connect(DB, read_only=True)
    rows = []
    for name, (raw, gold) in QUESTIONS.items():
        rt, rr = _measure(con, raw); gt, gr = _measure(con, gold)
        rows.append(dict(question=name, raw_ms=round(rt, 2), gold_ms=round(gt, 2),
                         raw_rows_scanned=rr, gold_rows_scanned=gr,
                         rows_scanned_reduction_pct=round(100 * (1 - gr / rr), 2) if rr else None,
                         speedup_x=round(rt / gt, 1) if gt else None))
    tot_raw = sum(r["raw_rows_scanned"] for r in rows); tot_gold = sum(r["gold_rows_scanned"] for r in rows)
    res = dict(questions=rows, total_raw_rows_scanned=tot_raw, total_gold_rows_scanned=tot_gold,
               total_rows_scanned_reduction_pct=round(100 * (1 - tot_gold / tot_raw), 2),
               median_speedup_x=statistics.median(r["speedup_x"] for r in rows))
    Path("results/finops_benchmark.json").write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
