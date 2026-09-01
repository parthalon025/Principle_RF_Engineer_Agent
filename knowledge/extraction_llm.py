"""I/O adapters that actually call an LLM to extract structured component
specifications from document chunk text (ADR-0003, ADR-0004).

Not to be confused with `knowledge/extraction.py`, which is docling-based
document *parsing* (ticket #8, deterministic, no LLM call). This module is
the LLM-based extraction step that runs over already-chunked, already-stored
document content (ticket #11).

`_extract_via_local` and `_extract_via_external` are two structurally
separate functions, mirroring `knowledge/embedding.py`'s pattern exactly and
for the same reason: `knowledge/extract.py` routes SENSITIVE/RESTRICTED
documents through `_extract_via_local` only, and that call path never
references `_extract_via_external` at all -- not behind a conditional, not
as a fallback. A bug in a shared function with a runtime backend check could
fail open (leak restricted datasheet content externally); two separate
functions can only fail closed (a stuck, unextracted document).

Both backends are the same kind of client -- an OpenAI-compatible chat
completions API, reached via base URL + key from config (ADR-0004) -- so
there's no per-deployment branching inside either function, only which
config it reads.

Thin I/O, not held to this repo's usual unit-test bar (mirrors
`knowledge/embedding.py`'s and `simulation/*`'s untested-boundary posture):
there's no live self-hosted model or network egress to arbitrary hosts in
this sandbox to test against, and no live LLM extraction endpoint reachable
here at all. `knowledge/extract.py`'s tests instead inject fakes for these
two functions to verify routing/backend-selection/no-fallback logic.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from knowledge.component_schema import CATEGORY_FIELDS

# No env var is specified for this in ticket #11's acceptance criteria (only
# the LOCAL_* triple below is implied by ADR-0004's pattern) -- a small,
# cheap chat model is used as a fixed default for the external backend.
EXTERNAL_EXTRACTION_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are extracting structured RF component specifications from datasheet "
    "text chunks. For each distinct orderable part described, return one "
    "component with its exact manufacturer part number, its category (one of: "
    f"{', '.join(CATEGORY_FIELDS.keys())}), and any of that category's known "
    "specification fields you can read a value for, each tagged 'high' "
    "confidence for a clean, unambiguous single-value read or 'low' for an "
    "ambiguous or inferred one. Category fields: "
    f"{json.dumps({k.value: list(v.keys()) for k, v in CATEGORY_FIELDS.items()})}. "
    'Respond as JSON: {"components": [{"manufacturer": str|null, '
    '"part_number": str, "category": str, "fields": {field_name: {"value": ..., '
    '"unit": str, "condition": str|null, "confidence": "high"|"low", '
    '"chunk_id": int, "page_number": int|null}}}]}'
)


class LocalExtractionUnavailableError(Exception):
    """Raised when the self-hosted extraction endpoint could not be reached
    or returned an error. Callers may catch this to fall back to the
    external API for PUBLIC/INTERNAL documents (ADR-0004) -- but never for
    SENSITIVE/RESTRICTED ones, which have no code path to that fallback."""


def _build_user_prompt(chunks: list[dict[str, Any]]) -> str:
    parts = []
    for chunk in chunks:
        parts.append(
            f"[chunk_id={chunk['id']} page={chunk.get('page_number')}]\n{chunk['content']}"
        )
    return "\n\n".join(parts)


def _parse_response(content: str) -> list[dict[str, Any]]:
    parsed = json.loads(content)
    return parsed.get("components", [])


def _extract_via_local(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract components from `chunks` via the self-hosted, OpenAI-compatible
    backend (`LOCAL_LLM_BASE_URL` / `LOCAL_LLM_API_KEY` / `LOCAL_EXTRACTION_MODEL`).

    Any failure to reach or use the endpoint -- including the backend simply
    not being configured yet, which is the common state before a self-hosted
    deployment exists -- is normalized to `LocalExtractionUnavailableError`
    so callers have one exception type to catch and PUBLIC/INTERNAL documents
    can fall back to the external API in every one of those cases, not just
    live connection failures.
    """
    try:
        base_url = os.environ["LOCAL_LLM_BASE_URL"]
        api_key = os.environ.get("LOCAL_LLM_API_KEY") or "unused"
        model = os.environ["LOCAL_EXTRACTION_MODEL"]
        client = OpenAI(base_url=base_url, api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(chunks)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
    except Exception as exc:  # normalize any config/client/connection failure
        raise LocalExtractionUnavailableError(
            f"self-hosted extraction backend unreachable or unconfigured: {exc}"
        ) from exc
    return _parse_response(content)


def _extract_via_external(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract components from `chunks` via OpenAI's own hosted API (`OPENAI_API_KEY`)."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=EXTERNAL_EXTRACTION_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(chunks)},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return _parse_response(content)
