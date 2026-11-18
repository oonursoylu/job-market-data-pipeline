import pytest

from src import config


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    """Point every archive path at a temporary folder."""
    monkeypatch.setattr(config, "RAW_DATA_DIR", tmp_path / "raw")
    return tmp_path / "raw"


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload


class FakeSession:
    """Returns one prepared response per request, in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def page(ids, description="Example snippet"):
    return FakeResponse(200, {"results": [{"id": str(i), "title": "Data Engineer", "description": description} for i in ids]})
