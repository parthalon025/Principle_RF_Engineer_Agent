"""I/O adapters that actually call an embedding backend (ADR-0004).

`_embed_via_local` and `_embed_via_external` are two structurally separate
functions rather than one shared function parameterized by backend. That's
deliberate: `knowledge/index.py` routes SENSITIVE/RESTRICTED documents
through `_embed_via_local` only, and that call path never references
`_embed_via_external` at all -- not behind a conditional, not as a fallback.
A bug in a shared function with a runtime backend check could fail open
(leak restricted content externally); two separate functions can only fail
closed (a stuck, unembedded document).

Both backends are the same kind of client -- an OpenAI-compatible API,
reached via base URL + key from config (ADR-0004) -- so there's no
per-deployment branching inside either function, only which config it reads.

Thin I/O, not held to this repo's usual unit-test bar (mirrors
`simulation/*`'s untested-boundary posture): there's no live self-hosted
model or network egress to arbitrary hosts in this sandbox to test against.
`knowledge/index.py`'s tests instead inject fakes for these two functions.
"""

from __future__ import annotations

import os

from openai import OpenAI

# No env var is specified for this in ticket #9's acceptance criteria (only
# LOCAL_EMBEDDING_MODEL is) -- OpenAI's small embedding model is used as a
# fixed default, matching EMBEDDING_DIM_EXTERNAL's own default of 1536.
EXTERNAL_EMBEDDING_MODEL = "text-embedding-3-small"


class LocalBackendUnavailableError(Exception):
    """Raised when the self-hosted embedding endpoint could not be reached
    or returned an error. Callers may catch this to fall back to the
    external API for PUBLIC/INTERNAL documents (ADR-0004) -- but never for
    SENSITIVE/RESTRICTED ones, which have no code path to that fallback."""


def _embed_via_local(texts: list[str]) -> list[list[float]]:
    """Embed `texts` via the self-hosted, OpenAI-compatible backend
    (`LOCAL_LLM_BASE_URL` / `LOCAL_LLM_API_KEY` / `LOCAL_EMBEDDING_MODEL`).

    Any failure to reach or use the endpoint -- including the backend simply
    not being configured yet (`LOCAL_LLM_BASE_URL`/`LOCAL_EMBEDDING_MODEL`
    unset), which is the common state before a self-hosted deployment
    exists -- is normalized to `LocalBackendUnavailableError` so callers
    have one exception type to catch and PUBLIC/INTERNAL documents can fall
    back to the external API in every one of those cases, not just live
    connection failures.
    """
    try:
        base_url = os.environ["LOCAL_LLM_BASE_URL"]
        api_key = os.environ.get("LOCAL_LLM_API_KEY") or "unused"
        model = os.environ["LOCAL_EMBEDDING_MODEL"]
        client = OpenAI(base_url=base_url, api_key=api_key)
        response = client.embeddings.create(model=model, input=texts)
    except Exception as exc:  # normalize any config/client/connection failure
        raise LocalBackendUnavailableError(
            f"self-hosted embedding backend unreachable or unconfigured: {exc}"
        ) from exc
    return [item.embedding for item in response.data]


def _embed_via_external(texts: list[str]) -> list[list[float]]:
    """Embed `texts` via OpenAI's own hosted API (`OPENAI_API_KEY`)."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.embeddings.create(model=EXTERNAL_EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]
