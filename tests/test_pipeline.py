from datetime import date

from src import run_pipeline


def test_pipeline_runs_extract_catch_up_and_load_in_order(monkeypatch):
    calls = []
    monkeypatch.setattr(run_pipeline, "extract_all", lambda day, resume: calls.append("extract") or 0)
    monkeypatch.setattr(run_pipeline, "catch_up", lambda day: calls.append("catch_up") or [])
    monkeypatch.setattr(run_pipeline, "load_date", lambda day: calls.append("load"))

    run_pipeline.run(date.today(), skip_extract=False, skip_dbt=True)
    assert calls == ["extract", "catch_up", "load"]


def test_a_past_date_skips_extraction(monkeypatch):
    calls = []
    monkeypatch.setattr(run_pipeline, "extract_all", lambda day, resume: calls.append("extract") or 0)
    monkeypatch.setattr(run_pipeline, "catch_up", lambda day: calls.append("catch_up") or [])
    monkeypatch.setattr(run_pipeline, "load_date", lambda day: calls.append("load"))

    run_pipeline.run(date(2026, 11, 3), skip_extract=False, skip_dbt=True)
    assert calls == ["catch_up", "load"]
