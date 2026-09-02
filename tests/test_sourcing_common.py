import pytest

import knowledge.sourcing_common as sc
from knowledge.sourcing_common import (
    ExternalNetworkToolsDisabledError,
    download_to_file,
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
