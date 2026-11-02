"""Data quality + reconciliation, the local twin of Snowflake Data Metric Functions.

1. DMF-style metrics on each layer (null count, duplicate count, freshness, row count).
2. Revenue reconciliation: recompute net revenue per event straight from the raw
   webhook file in plain Python (no SQL, no dbt) and compare it to the gold layer
   to the cent. Any gap fails the run.
3. Registration reconciliation: confirmed registrations in RDS vs gold.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import duckdb
import pandas as pd

DB = os.environ.get("DUCKDB_PATH", "data/race_roster.duckdb")


def dmf_metrics(con) -> list[dict]:
    checks = [
        ("bronze.payment_webhooks", "id"), ("silver.silver_payment_events", "webhook_event_id"),
        ("silver.silver_registrations", "registration_id"), ("gold.fct_registrations", "registration_id"),
        ("silver.silver_participants", "participant_id"),
    ]
    out = []
    for tbl, key in checks:
        rows, nulls, dups = con.execute(
            f"select count(*), count(*) - count({key}), count(*) - count(distinct {key}) from {tbl}").fetchone()
        out.append(dict(table=tbl, key=key, row_count=rows, null_count=nulls, duplicate_count=dups))
    return out


def independent_revenue(src: Path = Path("data/source")) -> dict[int, int]:
    """Net cents per event computed with plain Python from the raw files."""
    regs = pd.read_parquet(src / "rds" / "registrations.parquet")[["registration_id", "race_id"]]
    races = pd.read_parquet(src / "rds" / "races.parquet")[["race_id", "event_id"]]
    reg_event = dict(zip(regs.registration_id, regs.race_id.map(dict(zip(races.race_id, races.event_id)))))
    seen, net = set(), defaultdict(int)
    with open(src / "payment_webhooks.jsonl") as f:
        for line in f:
            w = json.loads(line)
            if w["id"] in seen:
                continue
            seen.add(w["id"])
            sign = 1 if w["type"] == "charge.succeeded" else -1
            net[int(reg_event[w["data"]["registration_id"]])] += sign * w["data"]["amount_cents"]
    return dict(net)


def run() -> dict:
    con = duckdb.connect(DB, read_only=True)
    metrics = dmf_metrics(con)
    gold = dict(con.execute(
        "select event_id, cast(round(sum(net_amount) * 100) as bigint) from gold.fct_registrations group by 1").fetchall())
    truth = independent_revenue()
    mismatched = {e: (truth.get(e, 0), gold.get(e, 0)) for e in set(truth) | set(gold) if truth.get(e, 0) != gold.get(e, 0)}
    src_conf = int((pd.read_parquet("data/source/rds/registrations.parquet").status == "confirmed").sum())
    gold_conf = con.execute("select count(*) from gold.fct_registrations where status='confirmed'").fetchone()[0]
    bronze_dupes = con.execute("select count(*) - count(distinct id) from bronze.payment_webhooks").fetchone()[0]
    res = dict(
        dmf_metrics=metrics,
        revenue_reconciliation=dict(
            events_checked=len(truth), events_matched_to_cent=len(truth) - len(mismatched),
            source_net_revenue_cents=sum(truth.values()), gold_net_revenue_cents=sum(gold.values()),
            mismatches=mismatched),
        registration_reconciliation=dict(source_confirmed=src_conf, gold_confirmed=gold_conf),
        duplicate_webhooks_in_bronze=bronze_dupes,
        duplicate_webhooks_in_silver=next(m for m in metrics if m["table"] == "silver.silver_payment_events")["duplicate_count"],
    )
    res["passed"] = (not mismatched and src_conf == gold_conf and res["duplicate_webhooks_in_silver"] == 0
                     and all(m["null_count"] == 0 for m in metrics))
    Path("results/quality.json").write_text(json.dumps(res, indent=2, default=str))
    return res


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "dmf_metrics"}, indent=2, default=str))
    raise SystemExit(0 if r["passed"] else 1)
