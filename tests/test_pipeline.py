import json
from pathlib import Path

import duckdb
import pytest

DB = "data/race_roster.duckdb"
R = Path("results")
pytestmark = pytest.mark.skipif(not Path(DB).exists(), reason="run python -m src.run_all first")


def load(f):
    return json.loads((R / f).read_text())


def test_revenue_reconciles_to_the_cent():
    r = load("quality.json")["revenue_reconciliation"]
    assert r["mismatches"] == {} and r["source_net_revenue_cents"] == r["gold_net_revenue_cents"]


def test_registrations_reconcile():
    r = load("quality.json")["registration_reconciliation"]
    assert r["source_confirmed"] == r["gold_confirmed"]


def test_bronze_keeps_duplicates_silver_removes_them():
    q = load("quality.json")
    assert q["duplicate_webhooks_in_bronze"] > 0 and q["duplicate_webhooks_in_silver"] == 0


def test_replay_safe():
    assert load("replay_check.json")["replay_safe"]


def test_no_raw_pii_in_gold_or_silver():
    con = duckdb.connect(DB, read_only=True)
    for schema in ("silver", "gold"):
        cols = con.execute(f"select table_name, column_name from information_schema.columns where table_schema='{schema}'").fetchall()
        assert not [c for c in cols if c[1] in ("email", "phone", "first_name", "last_name", "birth_date", "donor_email")]
    assert con.execute("select count(*) from silver.silver_participants where email_token like '%@%'").fetchone()[0] == 0


def test_gold_is_cheaper_than_raw():
    f = load("finops_benchmark.json")
    assert f["total_gold_rows_scanned"] < f["total_raw_rows_scanned"]


def test_model_beats_naive_forecast():
    f = load("forecast_eval.json")
    assert f["gradient_boosting"]["mape_pct"] < f["naive_double_midpoint"]["mape_pct"]


def test_dag_order():
    from dags.race_roster_dag import STEPS
    assert [s[0] for s in STEPS][:3] == ["ingest_bronze", "dbt_build_silver_gold", "quality_and_reconciliation"]
