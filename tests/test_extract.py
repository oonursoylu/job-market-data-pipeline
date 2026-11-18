import json
from datetime import date

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
    extract.set_aside_failed_status("gb", "data_engineer", DAY)
    assert run(FakeSession([page([1]), page([2])])) == 2
    folder = config.archive_dir("gb", "data_engineer", DAY)
    assert len(list(folder.glob("extraction_status.failed-*.json"))) == 1
    assert extract.segment_state("gb", "data_engineer", DAY) == "complete"
