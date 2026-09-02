"""Shared tool-permission enforcement, reading `policies/tool_policy.yaml`.

`/grill-with-docs` on the RF tool orchestration flow found that file was
never programmatically loaded anywhere -- it existed only as prose read by
humans (README.md, docs/adr/0005, a knowledge/read.py docstring), while the
real gates that exist (`measurement/base.py`'s `ApprovalReceipt`,
`orchestration/approval.py`'s `LoopStepApprovalReceipt`) were each built
independently, tool by tool, never consulting it. This module is the single
place both `agent/main.py` and `mcp_server/server.py` import for policy
enforcement, so the two tool surfaces cannot drift the way their (already
duplicated) tool *definitions* could.

TWO SEPARATE CHECKS, TWO SEPARATE PURPOSES:

  1. `assert_all_tools_categorized(tool_names)` -- an IMPORT-TIME
     completeness check. Call once, after a module has built its full list
     of registered tool names, with every name that module actually
     exposes. Raises `PolicyError` immediately if any name isn't
     classified under some category in `tool_policy.yaml` -- so a future
     tool added to `agent/main.py`/`mcp_server/server.py` without a
     matching policy entry fails to import at all, rather than silently
     running unguarded the first time someone calls it. This is the "fail
     closed for an unlisted tool" decision from the grilling session,
     implemented as a load-time assertion rather than a per-call check:
     strictly stronger (it can never even start serving), and touches
     exactly one call site per file instead of one at every one of the
     ~65 individual tool bodies.

  2. `enforce(tool_name)` -- a PER-CALL runtime gate for the two
     categories that actually carry a runtime rule:
       - `blocked_by_default` -> always raises `PolicyError`.
       - `approval_required` -> always raises `PolicyError` (every entry
         in that category today is a capability with no implementation to
         call in the first place -- see tool_policy.yaml's own comment on
         that category -- so this is unreachable in practice right now,
         same as `orchestration.approval.request_loop_step_approval`
         raising with no callback. It exists as the seam a real tool in
         that category would call once one is ever built, exactly
         mirroring how this project always defines an approval seam
         before wiring a real approval workflow behind it.)
     Every other category (`read_only`, `calculation`, `simulation_auto`,
     `approval_self_gated`, `approval_workflow`, `ingestion_auto`,
     `design_tracking`, `design_loop`) is a no-op here -- those tools
     either have no dangerous action to gate, or (approval_self_gated)
     already enforce their own independent gate
     (`measurement/base.py`/`simulation/hfss.py`), which this function
     deliberately does not duplicate or interfere with. `enforce()` is not
     currently called from any of the ~65 tool wrapper bodies in
     agent/main.py or mcp_server/server.py, because none of them fall in
     a category that would change behavior today -- it is here, tested,
     and ready for the wrapper a future `blocked_by_default`/
     `approval_required` tool would need.

Both checks share one loaded copy of the policy file (`_load_policy`,
cached) so a malformed `tool_policy.yaml` is caught the same way at either
call site.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "tool_policy.yaml"

# Categories enforce() treats as a hard, unconditional refusal. Every other
# category loaded from the file is documentation-only -- see this module's
# docstring.
_GATED_CATEGORIES = frozenset({"blocked_by_default", "approval_required"})


class PolicyError(RuntimeError):
    """Raised when a tool call is refused by `orchestration.policy` -- either
    because its category is a hard gate (`enforce`), or because it has no
    category at all (`assert_all_tools_categorized`)."""


@lru_cache(maxsize=1)
def _load_policy() -> dict[str, frozenset[str]]:
    """Load and cache `policies/tool_policy.yaml` as
    `{category: frozenset(tool_names)}`. Cached because this file changes
    only with a code deploy, never at runtime, and both
    `assert_all_tools_categorized` (import time, twice -- once per tool
    surface) and `enforce` (every gated call) read it."""
    with _POLICY_PATH.open() as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise PolicyError(f"{_POLICY_PATH} did not parse to a mapping of category -> tool list")
    return {category: frozenset(names or []) for category, names in raw.items()}


def _category_for(tool_name: str) -> str | None:
    for category, names in _load_policy().items():
        if tool_name in names:
            return category
    return None


def assert_all_tools_categorized(tool_names: Any) -> None:
    """Raise `PolicyError` naming every tool in `tool_names` that has no
    category anywhere in `tool_policy.yaml`. Call this once per tool
    surface (agent/main.py, mcp_server/server.py), after building the full
    list of tool names that surface registers, so an uncategorized tool
    fails at import time rather than being silently reachable.
    """
    policy = _load_policy()
    known = frozenset().union(*policy.values()) if policy else frozenset()
    uncategorized = sorted(set(tool_names) - known)
    if uncategorized:
        raise PolicyError(
            "The following tools are registered but not categorized in "
            f"{_POLICY_PATH.relative_to(_POLICY_PATH.parent.parent)} -- add "
            "each to exactly one category before this tool surface may load "
            f"(fail closed for an uncategorized tool): {uncategorized}"
        )


def enforce(tool_name: str) -> None:
    """Raise `PolicyError` if `tool_name`'s category is a hard gate
    (`blocked_by_default`, `approval_required`); otherwise return
    normally. Does nothing for a tool with no category at all -- that gap
    is `assert_all_tools_categorized`'s job, checked once at import time
    for the whole tool surface, not re-checked on every call.
    """
    category = _category_for(tool_name)
    if category not in _GATED_CATEGORIES:
        return
    raise PolicyError(
        f"{tool_name!r} is categorized {category!r} in tool_policy.yaml and "
        "is refused unconditionally: blocked_by_default tools never run; "
        "approval_required tools have no implementation reachable through "
        "this policy layer yet (see tool_policy.yaml's approval_required "
        "comment) -- a tool that already enforces its own approval gate "
        "(measurement/base.py, simulation/hfss.py) is categorized "
        "approval_self_gated instead, and is not affected by this check."
    )
