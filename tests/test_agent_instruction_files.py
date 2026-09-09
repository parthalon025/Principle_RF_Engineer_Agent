"""Issue #217: `CLAUDE.md` and `AGENTS.md` must stay byte-identical.

The repo ships the same agent instructions under two names because different
tools look for different filenames. Nothing enforced that they match, and
nothing would have noticed if they stopped: each file is separately plausible
on its own, so a drift is invisible on inspection and only shows up as two
agents behaving differently for reasons nobody can see.

*In plain terms: there are two copies of the house rules, and until this test
existed you could edit one and leave the other saying something else.*

The risk grew when the charter landed (ADR-0028's "What this program is for"),
which roughly tripled both files -- more surface, same absence of a guard.

**A test rather than a CI-only `diff` step**, deliberately: drift is
introduced on a laptop, so the check has to be runnable there. CI runs the
suite anyway, so a test is a superset of the workflow step, not an
alternative to it.

**Byte-identical rather than "equivalent"**, also deliberately: any weaker
rule needs a definition of equivalence, and the only honest one for a
document read by an LLM is that the bytes are the same. Copy one over the
other.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_AGENTS_MD = _REPO_ROOT / "AGENTS.md"


def test_both_agent_instruction_files_exist():
    """Neither file may be deleted in favour of the other.

    Checked separately from the comparison so a missing file reports itself
    as missing, rather than surfacing as a confusing content mismatch.
    """
    assert _CLAUDE_MD.is_file(), f"{_CLAUDE_MD.name} is missing"
    assert _AGENTS_MD.is_file(), f"{_AGENTS_MD.name} is missing"


def test_claude_md_and_agents_md_are_byte_identical():
    """The two files carry the same instructions, byte for byte.

    Read as bytes, not text: a difference in line endings or trailing
    whitespace is a real difference to whatever reads these files, and
    normalising it away here would let exactly that drift through.
    """
    claude_bytes = _CLAUDE_MD.read_bytes()
    agents_bytes = _AGENTS_MD.read_bytes()

    if claude_bytes == agents_bytes:
        return

    # Only reached on failure, so the cost of building a readable diff is
    # paid only when someone needs to read one.
    import difflib

    diff = "\n".join(
        difflib.unified_diff(
            claude_bytes.decode("utf-8", errors="replace").splitlines(),
            agents_bytes.decode("utf-8", errors="replace").splitlines(),
            fromfile="CLAUDE.md",
            tofile="AGENTS.md",
            lineterm="",
            n=1,
        )
    )
    raise AssertionError(
        "CLAUDE.md and AGENTS.md have drifted. They must stay byte-identical "
        "(issue #217). Fix by copying whichever one is correct over the "
        "other:\n\n    cp CLAUDE.md AGENTS.md\n\n"
        f"Difference:\n{diff}"
    )
