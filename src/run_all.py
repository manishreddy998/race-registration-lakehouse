"""End-to-end local run: synth -> dlt bronze -> dbt silver/gold -> quality -> finops -> forecast -> replay."""
import json
import os
import shutil
import time
from pathlib import Path

from src import dbt_runner, finops, forecast, ingest, quality, replay_check, synth


def main() -> None:
    db = Path(os.environ.get("DUCKDB_PATH", "data/race_roster.duckdb"))
    db.unlink(missing_ok=True); shutil.rmtree(".dlt_pipelines", ignore_errors=True)
    t0 = time.perf_counter(); steps = {}
    for name, fn in [("synth", lambda: Path("results/source_stats.json").write_text(json.dumps(synth.generate(), indent=2))),
                     ("ingest_bronze", ingest.run), ("dbt_build", dbt_runner.build), ("quality", quality.run),
                     ("finops", finops.run), ("forecast", forecast.run), ("replay", replay_check.run)]:
        s = time.perf_counter(); out = fn(); steps[name] = round(time.perf_counter() - s, 2)
        if name == "quality" and not out["passed"]:
            raise SystemExit("quality gate failed")
    Path("results/run_timings.json").write_text(json.dumps(dict(steps_seconds=steps, total_seconds=round(time.perf_counter() - t0, 2)), indent=2))
    print(json.dumps(steps, indent=2))


if __name__ == "__main__":
    main()
