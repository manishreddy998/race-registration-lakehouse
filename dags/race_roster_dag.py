"""Airflow DAG for the local / external-scheduler version of the pipeline.
In Snowflake the same flow runs as Dynamic Tables + Tasks (see snowflake/).
The README explains when each choice fits."""
from __future__ import annotations

from datetime import datetime

STEPS = [
    ("ingest_bronze", "src.ingest:run"),
    ("dbt_build_silver_gold", "src.dbt_runner:build"),
    ("quality_and_reconciliation", "src.quality:run"),
    ("finops_benchmark", "src.finops:run"),
    ("sellout_forecast", "src.forecast:run"),
]

try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator

    with DAG(dag_id="race_roster_lakehouse", start_date=datetime(2026, 11, 1), schedule="*/30 * * * *",
             catchup=False, max_active_runs=1, tags=["race-roster", "medallion"]) as dag:
        prev = None
        for task_id, target in STEPS:
            mod, fn = target.split(":")
            t = BashOperator(task_id=task_id, bash_command=f"cd {{{{ var.value.repo_dir }}}} && python -c 'import {mod} as m; m.{fn}()'",
                             retries=2)
            if prev:
                prev >> t
            prev = t
except ImportError:  # Airflow not installed (CI / local)
    dag = None
