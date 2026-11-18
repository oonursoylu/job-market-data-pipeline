import json
import os
from datetime import date

import psycopg2.errors
import pytest

from src import config
from src.extract import run_adzuna_extract as extract
from src.load import postgres_loader
from src.load import run_postgres_load as load
from src.load.job_mapper import map_adzuna_job
from src.load.run_postgres_load import validate_archive
from tests.conftest import FakeSession, page

DAY = date(2026, 11, 18)


def mapped(job_id, title="Data Engineer"):
    return map_adzuna_job({"id": job_id, "title": title}, "data_engineer", "gb", DAY)


def test_first_per_job_keeps_the_first_copy():
    jobs = [mapped("1", "first"), mapped("2"), mapped("1", "second")]
    kept = postgres_loader.first_per_job(jobs)
    assert [job["job_id"] for job in kept] == ["1", "2"]
    assert kept[0]["job_title"] == "first"


def test_a_changed_archive_fails_validation(raw_dir):
    extract.run_extract(FakeSession([page([1, 2])]), ("id", "key"), "gb", "data_engineer", DAY,
                        max_pages=1, results_per_page=2, pause_seconds=0)
    archive = config.archive_path("gb", "data_engineer", DAY)
    archive.write_text(archive.read_text().replace('"1"', '"7"'), encoding="utf-8")
    with pytest.raises(ValueError, match="inconsistent extraction status"):
        validate_archive("gb", "data_engineer", DAY)


needs_database = pytest.mark.skipif(
    not os.getenv("JOB_MARKET_TEST_DATABASE"),
    reason="Set JOB_MARKET_TEST_DATABASE to an empty test database to run database tests.",
)


@pytest.fixture
def connection(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", os.environ["JOB_MARKET_TEST_DATABASE"])
    connection = postgres_loader.get_connection()
    with connection, connection.cursor() as cursor:
        cursor.execute((config.PROJECT_ROOT / "sql" / "001_create_raw_schema.sql").read_text())
        cursor.execute("TRUNCATE raw.job_posting_observations, raw.job_postings")
    yield connection
    connection.close()


def table_counts(connection):
    with connection, connection.cursor() as cursor:
        cursor.execute("SELECT (SELECT count(*) FROM raw.job_postings), (SELECT count(*) FROM raw.job_posting_observations)")
        return cursor.fetchone()


@needs_database
def test_load_is_idempotent(connection):
    jobs = [mapped("1"), mapped("2"), mapped("1")]
    assert postgres_loader.load_segment(connection, jobs) == (2, 2)
    assert postgres_loader.load_segment(connection, jobs) == (0, 0)
    assert table_counts(connection) == (2, 2)


@needs_database
def test_a_failed_segment_leaves_nothing_behind(connection):
    broken = mapped("3")
    broken["search_country"] = None  # violates NOT NULL in both tables
    with pytest.raises(psycopg2.errors.NotNullViolation):
        postgres_loader.load_segment(connection, [mapped("4"), broken])
    assert table_counts(connection) == (0, 0)


@needs_database
def test_postings_and_observations_commit_together(connection, monkeypatch):
    def fail(cursor, jobs):
        raise RuntimeError("observation insert failed")

    monkeypatch.setattr(postgres_loader, "insert_job_posting_observations", fail)
    with pytest.raises(RuntimeError):
        postgres_loader.load_segment(connection, [mapped("5")])
    assert table_counts(connection) == (0, 0)


def make_archive(country, role, day, records=1):
    path = config.archive_path(country, role, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"id": str(i)}) + "\n" for i in range(records)), encoding="utf-8")


def make_full_day(day):
    for country, role in config.expected_segments(day):
        make_archive(country, role, day)
    return {(day, country, role) for country, role in config.expected_segments(day)}


def test_catch_up_finds_days_that_are_not_fully_loaded(raw_dir):
    run_day = date(2026, 11, 20)
    loaded = make_full_day(date(2026, 11, 18))                                  # fully loaded
    loaded |= make_full_day(date(2026, 11, 16)) - {(date(2026, 11, 16), "gb", "ai_engineer")}
    make_full_day(run_day)                                                      # the run date itself
    make_archive("de", "data_engineer", date(2026, 10, 1))                      # outside the window
    make_archive("gb", "data_analyst", date(2026, 11, 13), records=0)           # empty: nothing to load

    assert load.dates_to_catch_up(run_day, loaded, lookback_days=14) == [date(2026, 11, 16)]


class FakeConnection:
    def close(self):
        pass


def test_catch_up_loads_what_it_can_and_reports_the_rest(raw_dir, monkeypatch):
    make_full_day(date(2026, 11, 13))
    make_full_day(date(2026, 11, 16))
    calls = []

    def fake_load(day, *args, **kwargs):
        calls.append(day)
        if day == date(2026, 11, 13):
            raise FileNotFoundError("Missing archives")

    monkeypatch.setattr(load, "get_connection", FakeConnection)
    monkeypatch.setattr(load, "loaded_segments", lambda connection, since: set())
    monkeypatch.setattr(load, "load_date", fake_load)

    assert load.catch_up(date(2026, 11, 18)) == [date(2026, 11, 16)]
    assert calls == [date(2026, 11, 13), date(2026, 11, 16)]


@needs_database
def test_loaded_segments_reads_what_is_in_the_database(connection):
    postgres_loader.load_segment(connection, [mapped("6")])
    assert load.loaded_segments(connection, DAY) == {(DAY, "gb", "data_engineer")}
    assert load.loaded_segments(connection, date(2026, 11, 19)) == set()
