"""Minimal stdlib HTTP GET helper shared by this package's five thin
ingestion clients (threegpp.py, etsi.py, fcc_ecfr.py, arxiv.py, patent.py).

Uses `urllib.request` from the standard library rather than adding a new
HTTP dependency: `requests` is not in this project's dependency tree
(see pyproject.toml), and none of the five sources this package talks to
need anything beyond a plain unauthenticated GET -- confirmed individually
per source, see each calling module's own docstring. Matches this repo's
"improve before adding" convention of not pulling in a new third-party
dependency for something the standard library already covers.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request

_DEFAULT_TIMEOUT_S = 60

# "Retries ... 2-3 times with backoff" (issue #405). 3 retries -> 4 attempts
# total. Kept small and bounded on purpose: an ingest that is still failing
# after 4 tries almost never fixes itself on a 5th, and the caller (a human
# running an ingest command) is better served by a fast, clear failure than
# a long hang.
_DEFAULT_MAX_RETRIES = 3
# Exponential backoff seasoned with this base: 0.5s, 1s, 2s between the 1st,
# 2nd, 3rd and 4th attempts -- enough for a transient blip (a dropped
# connection, a momentarily overloaded server) to clear without turning a
# failed ingest into a multi-minute wait.
_DEFAULT_BACKOFF_BASE_S = 0.5

# arXiv's own Terms of Use (https://info.arxiv.org/help/api/tou.html) ask
# automated clients to send "a descriptive User-Agent string". Applied here
# as a general good-citizen default for all five sources this package
# talks to, not just arXiv.
_USER_AGENT = (
    "PrincipalRFEngineerAgent-knowledge-sourcing/1.0 "
    "(+https://github.com/parthalon025/Principle_RF_Engineer_Agent)"
)


def _is_transient(exc: urllib.error.URLError) -> bool:
    """True for a failure worth retrying, false for one that will not
    change on a second try.

    A 5xx (`HTTPError` with `code >= 500`) is the server's own problem and
    often clears on its own -- worth retrying. A 4xx (`code < 500`, e.g.
    404 Not Found or 403 Forbidden) means the request itself is wrong;
    retrying it burns time for the same answer, so it is treated as
    permanent (issue #405's second acceptance criterion). Any other
    `URLError` -- a timeout, a dropped connection, a DNS hiccup -- carries
    no status code at all and is always transient.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500
    return True


def download_bytes(
    url: str,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> bytes:
    """GET `url` and return the raw response body.

    No credentials of any kind are sent -- every caller in this package
    talks to a source confirmed (per that calling module's own docstring)
    to need no authentication for the endpoints it hits.

    Retries a transient failure (a network-level error, or an HTTP 5xx
    response) up to `max_retries` times with a short exponential backoff
    between attempts before giving up and re-raising. An HTTP 4xx response
    is never retried -- it fails on the first attempt, exactly as before
    this wrapper existed. Content the server happily returns (a 200 with
    the wrong bytes -- an HTML error page instead of a PDF, say) is not
    this function's concern either: it has no opinion on body content, so
    that response is returned as-is, once, for the caller to validate --
    `patent.py`'s own `%PDF` magic-byte check is the existing example.
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
                return response.read()
        except urllib.error.URLError as exc:  # HTTPError is a URLError subclass
            if attempt >= max_retries or not _is_transient(exc):
                raise
            time.sleep(_DEFAULT_BACKOFF_BASE_S * (2**attempt))
            attempt += 1
