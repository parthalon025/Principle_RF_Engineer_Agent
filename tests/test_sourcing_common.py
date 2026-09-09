import json

import pytest

import knowledge.sourcing_common as sc
from knowledge.sourcing_common import (
    ExternalNetworkToolsDisabledError,
    download_to_file,
    post_json,
    require_external_network_tools_enabled,
)


def test_require_external_network_tools_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_EXTERNAL_NETWORK_TOOLS", raising=False)
    with pytest.raises(ExternalNetworkToolsDisabledError, match="TestSource"):
        require_external_network_tools_enabled("TestSource")


def test_require_external_network_tools_disabled_when_explicitly_false(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "false")
    with pytest.raises(ExternalNetworkToolsDisabledError):
        require_external_network_tools_enabled("TestSource")


def test_require_external_network_tools_enabled_when_true(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "true")
    require_external_network_tools_enabled("TestSource")  # must not raise


def test_require_external_network_tools_enabled_case_insensitive(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_NETWORK_TOOLS", "TRUE")
    require_external_network_tools_enabled("TestSource")  # must not raise


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_download_to_file_writes_bytes_and_derives_filename_from_url(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sc.urllib.request, "urlopen", lambda req, timeout=60: _FakeResponse(b"%PDF-1.4 fake")
    )

    dest = download_to_file("https://example.com/datasheets/PART123.pdf", tmp_path)

    assert dest.name == "PART123.pdf"
    assert dest.parent == tmp_path
    assert dest.read_bytes() == b"%PDF-1.4 fake"


def test_download_to_file_falls_back_to_generic_name_for_empty_url_path(tmp_path, monkeypatch):
    monkeypatch.setattr(sc.urllib.request, "urlopen", lambda req, timeout=60: _FakeResponse(b"x"))

    dest = download_to_file("https://example.com/?id=123", tmp_path)

    assert dest.name == "datasheet.pdf"


def test_download_to_file_creates_missing_dest_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sc.urllib.request, "urlopen", lambda req, timeout=60: _FakeResponse(b"x"))
    missing_dir = tmp_path / "nested" / "dir"

    dest = download_to_file("https://example.com/x.pdf", missing_dir)

    assert dest.exists()
    assert dest.parent == missing_dir


def test_post_json_sends_method_url_data_and_headers_and_parses_response(monkeypatch):
    """The one seam every credentialed POST client (Digi-Key, Mouser, Nexar,
    and USPTO ODP search) relies on -- see `post_json`'s own docstring."""
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=30):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["data"] = req.data
        captured["headers"] = req.headers
        captured["timeout"] = timeout
        return _FakeResponse(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(sc.urllib.request, "urlopen", fake_urlopen)

    result = post_json(
        "https://example.com/search",
        b'{"q": "metamaterial"}',
        {"X-Api-Key": "secret", "Content-Type": "application/json"},
    )

    assert result == {"ok": True}
    assert captured["url"] == "https://example.com/search"
    assert captured["method"] == "POST"
    assert captured["data"] == b'{"q": "metamaterial"}'
    # urllib.request.Request title-cases header names it is given.
    assert captured["headers"] == {"X-api-key": "secret", "Content-type": "application/json"}
    assert captured["timeout"] == 30


def test_post_json_honors_custom_timeout(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=30):
        captured["timeout"] = timeout
        return _FakeResponse(b"{}")

    monkeypatch.setattr(sc.urllib.request, "urlopen", fake_urlopen)

    post_json("https://example.com", b"{}", {}, timeout=5)

    assert captured["timeout"] == 5


def test_post_json_returns_empty_dict_for_empty_json_object(monkeypatch):
    monkeypatch.setattr(sc.urllib.request, "urlopen", lambda req, timeout=30: _FakeResponse(b"{}"))

    assert post_json("https://example.com", b"{}", {}) == {}
