from datetime import date

from src import config


def test_seeds_define_countries_and_roles():
    assert config.COUNTRY_CODES == ["de", "gb"]
    assert config.ROLE_CODES == ["data_engineer", "analytics_engineer", "ai_engineer", "data_analyst"]
    assert config.SEARCH_TERMS["data_analyst"] == "data analyst"


def test_expected_segments_follow_start_dates():
    assert config.expected_segments(date(2026, 6, 3)) == [("de", "data_engineer")]
    assert len(config.expected_segments(date(2026, 6, 16))) == 6
    assert ("gb", "data_analyst") not in config.expected_segments(date(2026, 9, 5))
    assert len(config.expected_segments(date(2026, 9, 6))) == 8


def test_expected_segments_respect_filters():
    assert config.expected_segments(date(2026, 11, 3), ["gb"], ["data_analyst"]) == [("gb", "data_analyst")]
