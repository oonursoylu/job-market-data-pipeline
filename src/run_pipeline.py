"""One pipeline run: collect today's adverts, load them, then run dbt.

Run from the repository root:

    python -m src.run_pipeline

Each step stops the run if it fails, so a bad extraction never reaches the
database and a failed load never reaches dbt. Rerunning on the same day is
safe: complete segments are skipped, failed or stale ones are retried, the
load ignores rows it already has, and dbt rebuilds the models.

Before loading the run date, it also loads any day from the last 14 days whose
archives are on disk but not fully in PostgreSQL (CATCH_UP_DAYS in config.py).

Everything printed is also appended to logs/pipeline_YYYY-MM-DD.log.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import date, datetime

from src.config import DBT_PROJECT_DIR, LOG_DIR, PROJECT_ROOT
from src.extract.run_adzuna_extract import extract_all
from src.load.run_postgres_load import catch_up, load_date, parse_date


class Tee:
    """Write to the console and a log file at the same time."""

    def __init__(self, *streams):
        self.streams = [stream for stream in streams if stream is not None]

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def find_dbt() -> str:
    # Prefer the dbt installed next to this Python, so a scheduled task does
    # not depend on PATH or an activated virtual environment.
    local = os.path.join(os.path.dirname(sys.executable), "dbt.exe" if os.name == "nt" else "dbt")
    if os.path.isfile(local):
        return local
    found = shutil.which("dbt")
    if not found:
        raise FileNotFoundError("dbt was not found. Install requirements.txt in this environment.")
    return found


def run_dbt(*args: str) -> int:
    command = [find_dbt(), *args, "--project-dir", str(DBT_PROJECT_DIR)]
    print("$ dbt " + " ".join(args), flush=True)
    environment = {**os.environ, "DBT_USE_COLORS": "false", "PYTHONIOENCODING": "utf-8"}
    with subprocess.Popen(command, cwd=PROJECT_ROOT, env=environment, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as process:
        for line in process.stdout:
            print(line, end="")
    return process.returncode


def step(title: str) -> None:
    print(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S}  {title} ===", flush=True)


def run(run_date: date, skip_extract: bool, skip_dbt: bool) -> None:
    if skip_extract or run_date != date.today():
        print("Skipping extraction.")
    else:
        step("1/3 Extract from Adzuna")
        print(f"Fetched {extract_all(run_date, resume=True)} records.")

    step("2/3 Validate and load into PostgreSQL")
    catch_up(run_date)
    print(f"\nLoading {run_date}:")
    load_date(run_date)

    if skip_dbt:
        return
    step("3/3 dbt source freshness and build")
    if run_dbt("source", "freshness") != 0:
        print("Warning: source freshness reported stale data; continuing to the build.")
    if run_dbt("build") != 0:
        raise RuntimeError("dbt build failed; see the dbt output above.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run extraction, load and dbt for one date.")
    parser.add_argument("--date", type=parse_date, default=date.today(), dest="run_date",
                        help="Date to load and build (default: today). Extraction only runs for today.")
    parser.add_argument("--skip-extract", action="store_true", help="Load existing archives only.")
    parser.add_argument("--skip-dbt", action="store_true", help="Stop after loading PostgreSQL.")
    args = parser.parse_args(argv)

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"pipeline_{date.today():%Y-%m-%d}.log"
    with log_path.open("a", encoding="utf-8") as log_file:
        sys.stdout = Tee(sys.__stdout__, log_file)
        sys.stderr = Tee(sys.__stderr__, log_file)
        started = time.monotonic()
        try:
            step(f"Pipeline run for {args.run_date}")
            run(args.run_date, args.skip_extract, args.skip_dbt)
            print(f"\nPIPELINE SUCCEEDED in {time.monotonic() - started:.0f} s\n", flush=True)
            return 0
        except Exception:
            traceback.print_exc()
            print(f"\nPIPELINE FAILED after {time.monotonic() - started:.0f} s\n", flush=True)
            return 1
        finally:
            sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__


if __name__ == "__main__":
    sys.exit(main())
