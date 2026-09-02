"""Minimal stdlib HTTP GET helper shared by this package's four thin
ingestion clients (threegpp.py, etsi.py, fcc_ecfr.py, arxiv.py).

Uses `urllib.request` from the standard library rather than adding a new
HTTP dependency: `requests` is not in this project's dependency tree
(see pyproject.toml), and none of the four sources this package talks to
need anything beyond a plain unauthenticated GET -- confirmed individually
per source, see each calling module's own docstring. Matches this repo's
"improve before adding" convention of not pulling in a new third-party
dependency for something the standard library already covers.
"""

from __future__ import annotations

import urllib.request

_DEFAULT_TIMEOUT_S = 60

# arXiv's own Terms of Use (https://info.arxiv.org/help/api/tou.html) ask
# automated clients to send "a descriptive User-Agent string". Applied here
# as a general good-citizen default for all four sources this package
# talks to, not just arXiv.
_USER_AGENT = (
    "PrincipalRFEngineerAgent-knowledge-sourcing/1.0 "
    "(+https://github.com/parthalon025/Principle_RF_Engineer_Agent)"
)


def download_bytes(url: str, timeout_s: int = _DEFAULT_TIMEOUT_S) -> bytes:
    """GET `url` and return the raw response body.

    No credentials of any kind are sent -- every caller in this package
    talks to a source confirmed (per that calling module's own docstring)
    to need no authentication for the endpoints it hits.
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        return response.read()
