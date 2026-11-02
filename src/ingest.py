"""ELT ingestion with dlt (data load tool) into the bronze layer.

- RDS tables: incremental on `updated_at` / primary key, so reruns only pull new rows.
  Locally the RDS snapshot is Parquet; in production swap the resource for
  dlt's `sql_database` source pointed at the AWS RDS Postgres read replica.
- Payment webhooks: loaded append-only, exactly as delivered (duplicates and
  out-of-order events kept) so bronze preserves the raw state for lineage.
  Dedup happens in silver, never in bronze.
Destination is DuckDB locally; set DESTINATION=snowflake to load Snowflake.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import dlt
import pyarrow.parquet as pq

SRC = Path("data/source")
DB = os.environ.get("DUCKDB_PATH", "data/race_roster.duckdb")
PKS = dict(events="event_id", races="race_id", price_tiers="price_tier_id",
           participants="participant_id", registrations="registration_id",
           fundraising_pages="fundraising_page_id", donations="donation_id")


def rds_table(name: str):
    pk = PKS[name]

    @dlt.resource(name=f"rds_{name}", primary_key=pk, write_disposition="merge")
    def _res():
        yield pq.read_table(SRC / "rds" / f"{name}.parquet")
    return _res


@dlt.resource(name="payment_webhooks", write_disposition="append")
def payment_webhooks():
    with open(SRC / "payment_webhooks.jsonl") as f:
        batch = []
        for line in f:
            row = json.loads(line)
            row["raw_payload"] = line.strip()  # keep exact bytes received
            batch.append(row)
            if len(batch) == 5000:
                yield batch
                batch = []
        if batch:
            yield batch


@dlt.source(name="race_roster")
def race_roster_source():
    return [rds_table(n)() for n in PKS] + [payment_webhooks()]


def run() -> dict:
    dest = os.environ.get("DESTINATION", "duckdb")
    destination = dlt.destinations.duckdb(DB) if dest == "duckdb" else dest
    pipe = dlt.pipeline(pipeline_name="race_roster_elt", destination=destination,
                        dataset_name="bronze", pipelines_dir=".dlt_pipelines")
    t0 = time.perf_counter()
    info = pipe.run(race_roster_source())
    secs = time.perf_counter() - t0
    counts = {}
    with pipe.sql_client() as c:
        for n in list(PKS) + ["webhooks"]:
            tbl = f"rds_{n}" if n != "webhooks" else "payment_webhooks"
            counts[tbl] = c.execute_sql(f"select count(*) from {tbl}")[0][0]
    stats = dict(destination=dest, load_seconds=round(secs, 2), bronze_row_counts=counts,
                 load_ids=list(info.loads_ids))
    Path("results").mkdir(exist_ok=True)
    Path("results/ingest_stats.json").write_text(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
