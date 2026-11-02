"""Run dbt build from Python (used by the DAG, CI and run_all)."""
from __future__ import annotations

import os
import subprocess
import sys


def build(select: str | None = None) -> None:
    env = dict(os.environ, DUCKDB_PATH=os.path.abspath(os.environ.get("DUCKDB_PATH", "data/race_roster.duckdb")))
    cmd = ["dbt", "build", "--profiles-dir", ".", "--project-dir", "."]
    if select:
        cmd += ["--select", select]
    subprocess.run(cmd, cwd="dbt", env=env, check=True)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
