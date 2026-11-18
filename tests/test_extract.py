import json
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

from src import config
from src.extract import run_adzuna_extract as extract
from src.extract.adzuna_client import AdzunaRequestError, fetch_jobs
from src.load.run_postgres_load import validate_archive
from tests.conftest import FakeResponse, FakeSession, page

DAY = date(2026, 11, 18)
CREDENTIALS = ("my-app-id", "secret-key-123")


def run(session, country="gb", role="data_engineer", pages=2):
    return extract.run_extract(session, CREDENTIALS, country, role, DAY,
                               max_pages=pages, results_per_page=2, pause_seconds=0)


def test_archive_and_status_pass_the_loader_checks(raw_dir):
    session = FakeSession([page([1, 2]), page([3])])
    assert run(session) == 3
    records = validate_archive("gb", "data_engineer", DAY)
    assert [record["id"] for record in records] == ["1", "2", "3"]
    assert session.calls[0][1]["what"] == "data engineer"


def test_existing_archive_is_never_overwritten(raw_dir):
    run(FakeSession([page([1]), page([2])]))
    with pytest.raises(FileExistsError):
        run(FakeSession([page([9]), page([9])]))


def test_failed_request_leaves_a_failed_status_and_no_archive(raw_dir):
    with pytest.raises(AdzunaRequestError):
        run(FakeSession([page([1]), FakeResponse(503)]))
    status = json.loads(config.status_path("gb", "data_engineer", DAY).read_text())
    assert status["status"] == "failed"
    assert not config.archive_path("gb", "data_engineer", DAY).exists()
    assert extract.segment_state("gb", "data_engineer", DAY) == "failed"


def test_error_messages_never_contain_the_api_key():
    url_error = requests.ConnectionError("Max retries exceeded with url: /jobs?app_key=secret-key-123")
    for response in (url_error, FakeResponse(403), FakeResponse(200, None)):
        with pytest.raises(AdzunaRequestError) as error:
            fetch_jobs(FakeSession([response]), CREDENTIALS, "gb", "data engineer")
        assert "secret-key-123" not in str(error.value)
        assert error.value.__cause__ is None


def test_resume_skips_complete_retries_failed_and_blocks_in_progress(raw_dir):
    run(FakeSession([page([1]), page([2])]), role="data_engineer")
    with pytest.raises(AdzunaRequestError):
        run(FakeSession([FakeResponse(500)]), role="analytics_engineer")
    in_progress = config.status_path("gb", "ai_engineer", DAY)
    in_progress.parent.mkdir(parents=True)
    in_progress.write_text(json.dumps({"status": "in_progress"}))

    with pytest.raises(FileExistsError):
        extract.plan_segments(DAY, ["gb"], ["data_engineer", "analytics_engineer", "ai_engineer"], resume=True)
    planned = extract.plan_segments(DAY, ["gb"], ["data_engineer", "analytics_engineer"], resume=True)
    assert planned == [("gb", "analytics_engineer")]
    with pytest.raises(FileExistsError):
        extract.plan_segments(DAY, ["gb"], ["data_engineer"], resume=False)


def test_failed_status_is_kept_when_a_segment_is_retried(raw_dir):
    with pytest.raises(AdzunaRequestError):
        run(FakeSession([FakeResponse(500)]))
    extract.set_aside_status("gb", "data_engineer", DAY, "failed")
    assert run(FakeSession([page([1]), page([2])])) == 2
    folder = config.archive_dir("gb", "data_engineer", DAY)
    assert len(list(folder.glob("extraction_status.failed-*.json"))) == 1
    assert extract.segment_state("gb", "data_engineer", DAY) == "complete"


def write_status(role, status, started_at):
    path = config.status_path("gb", role, DAY)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": status, "started_at": started_at.isoformat()}))


def test_an_old_in_progress_is_retried_but_a_recent_one_blocks(raw_dir):
    now = datetime.now(timezone.utc)
    write_status("data_engineer", "in_progress", now - timedelta(hours=2))
    write_status("analytics_engineer", "in_progress", now - timedelta(minutes=5))

    assert extract.segment_state("gb", "data_engineer", DAY) == "stale"
    assert extract.segment_state("gb", "analytics_engineer", DAY) == "blocked"
    assert extract.plan_segments(DAY, ["gb"], ["data_engineer"], resume=True) == [("gb", "data_engineer")]
    with pytest.raises(FileExistsError):
        extract.plan_segments(DAY, ["gb"], ["data_engineer"], resume=False)
    with pytest.raises(FileExistsError):
        extract.plan_segments(DAY, ["gb"], ["analytics_engineer"], resume=True)


def test_resume_keeps_stale_and_failed_statuses_and_collects_again(raw_dir, monkeypatch):
    write_status("data_engineer", "in_progress", datetime.now(timezone.utc) - timedelta(hours=3))
    with pytest.raises(AdzunaRequestError):
        run(FakeSession([FakeResponse(500)]), role="analytics_engineer")

    session = FakeSession([page([i]) for i in range(1, 7)])  # two segments, three pages each
    monkeypatch.setattr(extract, "build_session", lambda: session)
    monkeypatch.setattr(extract, "load_credentials", lambda: CREDENTIALS)
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)

    assert extract.extract_all(DAY, ["gb"], ["data_engineer", "analytics_engineer"], resume=True) == 6
    stale_folder = config.archive_dir("gb", "data_engineer", DAY)
    failed_folder = config.archive_dir("gb", "analytics_engineer", DAY)
    assert len(list(stale_folder.glob("extraction_status.stale-*.json"))) == 1
    assert len(list(failed_folder.glob("extraction_status.failed-*.json"))) == 1
    assert extract.segment_state("gb", "data_engineer", DAY) == "complete"
    assert extract.segment_state("gb", "analytics_engineer", DAY) == "complete"
