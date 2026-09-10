"""Tests for `knowledge.sourcing._http.download_bytes`'s retry/backoff
wrapper (issue #405).

`download_bytes` is the one-call-does-it-all seam shared by every ingestion
client in `knowledge/sourcing/` (see that package's own `__init__.py`
docstring). Before this ticket it made exactly one HTTP attempt and raised
whatever `urllib.request.urlopen` raised -- a transient network blip (a
timeout, a connection reset, a 502 from an overloaded server) failed the
whole ingest even though trying again a moment later would likely have
worked. These tests pin down the two behaviours the ticket asks for: retry
a transient failure a bounded number of times before giving up, and never
retry a 4xx (the request itself is wrong; trying again changes nothing).
"""

from __future__ import annotations

import urllib.error

import pytest

import knowledge.sourcing._http as http_mod
from knowledge.sourcing._http import download_bytes


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Retries back off with `time.sleep` -- stub it so the test suite
    doesn't actually pause, and so a test can assert on call count without
    caring about timing."""
    monkeypatch.setattr(http_mod.time, "sleep", lambda seconds: None)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://example.com/paper.pdf",
        code=code,
        msg="error",
        hdrs=None,
        fp=None,
    )


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_transient_failure_then_success_succeeds_overall(monkeypatch):
    """A connection drop (or any other transient network error) followed by
    a working attempt must still return the bytes -- the whole point of
    retrying is that the caller never sees the first failure."""
    calls = {"n": 0}

    def flaky_urlopen(request, timeout=60):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("connection reset by peer")
        return _FakeResponse(b"%PDF-1.4 real content")

    monkeypatch.setattr(http_mod.urllib.request, "urlopen", flaky_urlopen)

    result = download_bytes("https://example.com/paper.pdf")

    assert result == b"%PDF-1.4 real content"
    assert calls["n"] == 3


def test_persistent_5xx_is_retried_then_raises_after_giving_up(monkeypatch):
    """A 5xx that never recovers must still eventually surface to the
    caller as a failure -- retrying is bounded, not infinite."""
    calls = {"n": 0}

    def always_502(request, timeout=60):
        calls["n"] += 1
        raise _http_error(502)

    monkeypatch.setattr(http_mod.urllib.request, "urlopen", always_502)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        download_bytes("https://example.com/paper.pdf")

    assert exc_info.value.code == 502
    # At least one retry happened (not a single bare attempt), and it gave
    # up after a small, bounded number of tries rather than looping forever.
    assert 2 <= calls["n"] <= 4


def test_persistent_4xx_fails_immediately_without_retrying(monkeypatch):
    """A 404/403/etc. means the request itself is wrong -- trying again
    won't change the answer, so `download_bytes` must not retry at all."""
    calls = {"n": 0}

    def always_404(request, timeout=60):
        calls["n"] += 1
        raise _http_error(404)

    monkeypatch.setattr(http_mod.urllib.request, "urlopen", always_404)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        download_bytes("https://example.com/paper.pdf")

    assert exc_info.value.code == 404
    assert calls["n"] == 1


def test_first_attempt_success_needs_no_retry(monkeypatch):
    """The common case -- no failure at all -- must still work and must
    not sleep or loop unnecessarily."""
    calls = {"n": 0}

    def works_first_try(request, timeout=60):
        calls["n"] += 1
        return _FakeResponse(b"ok")

    monkeypatch.setattr(http_mod.urllib.request, "urlopen", works_first_try)

    assert download_bytes("https://example.com/x.pdf") == b"ok"
    assert calls["n"] == 1


def test_structurally_invalid_response_is_not_a_urllib_error_and_is_not_retried(monkeypatch):
    """A 'genuinely bad PDF' (issue #405's phrase) is a successful HTTP
    response with wrong content -- `download_bytes` has no opinion on body
    content, so it must simply return the bytes as-is, once, and let the
    caller (e.g. `patent.py`'s own `%PDF` magic-byte check) decide it's bad."""
    calls = {"n": 0}

    def returns_html_error_page(request, timeout=60):
        calls["n"] += 1
        return _FakeResponse(b"<html>not a pdf</html>")

    monkeypatch.setattr(http_mod.urllib.request, "urlopen", returns_html_error_page)

    assert download_bytes("https://example.com/x.pdf") == b"<html>not a pdf</html>"
    assert calls["n"] == 1
