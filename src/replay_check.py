"""Replay safety: the payment processor (or we) can resend the whole webhook
history. Load it into bronze a second time, rebuild, and prove gold money does
not change. Bronze keeps every delivery; silver dedups."""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb

from src import dbt_runner, ingest, quality

DB = os.environ.get("DUCKDB_PATH", "data/race_roster.duckdb")


def _gold_net() -> int:
    con = duckdb.connect(DB, read_only=True)
    v = con.execute("select cast(round(sum(net_amount)*100) as bigint) from gold.fct_registrations").fetchone()[0]
    con.close()
    return v


def run() -> dict:
    before = _gold_net()
    ingest.run()           # second full delivery of every webhook
    dbt_runner.build()
    q = quality.run()
    res = dict(gold_net_cents_before=before, gold_net_cents_after_replay=_gold_net(),
               bronze_duplicate_deliveries_after_replay=q["duplicate_webhooks_in_bronze"],
               silver_duplicates_after_replay=q["duplicate_webhooks_in_silver"],
               reconciliation_passed_after_replay=q["passed"])
    res["replay_safe"] = res["gold_net_cents_before"] == res["gold_net_cents_after_replay"] and q["passed"]
    Path("results/replay_check.json").write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    r = run(); print(json.dumps(r, indent=2)); raise SystemExit(0 if r["replay_safe"] else 1)
