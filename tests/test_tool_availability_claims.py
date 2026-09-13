"""A consistency check between what this repo CLAIMS about tool availability
(in docstrings, comments, and docs/tools/*.md -- see issue #480's sweep) and
what is actually on PATH -- so the next drift is caught mechanically rather
than reasoned about by hand the way issue #480 itself had to be.

THE FOUR-CASE FRAMEWORK issue #480 established (its own words): a tool
adapter's "not installed" caveat can mean any of (1) the binary is genuinely
absent everywhere; (2) present but not on PATH; (3) present and on PATH but
its Python bindings aren't importable from the app interpreter; (4) present,
on PATH, and one of its code paths is broken. This test covers case 1 vs
"present in this project's own Docker image, absent on a bare host" only --
the shape every corrected site in this sweep actually needed. It is NOT a
functional check that any solver actually runs correctly (that is each
adapter's own fake-executable test suite); it only checks presence-on-PATH,
the same fact the corrected docstrings now state.

WHY A CONTAINER MARKER, NOT A HOSTNAME OR ENV VAR THIS REPO INVENTED. Docker
creates `/.dockerenv` inside every container by convention (unrelated to
this repo, so it needs no Dockerfile change to rely on) -- a reliable signal
that this test is running where the Dockerfile's RUN steps actually
executed, as opposed to a bare checkout (this sandbox) or CI (also a bare
checkout, confirmed by every adapter's own test file already skipping the
same way). `_EXPECTED_ON_PATH_IN_IMAGE`'s assertions run ONLY inside a
container; everywhere else they skip with a stated reason -- exactly what
the acceptance criterion asks for ("skipped with a stated reason elsewhere"),
and it means this test can be shown to skip correctly here even though it
cannot be shown to pass here (no Docker daemon in this sandbox to build and
enter the image against).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

_RUNNING_IN_A_CONTAINER = Path("/.dockerenv").exists()

# Every one of these is confirmed, in the built image, on PATH -- see issue
# #480's own verification table (binary name -> where the Dockerfile puts
# it) and the Dockerfile's own RUN/ENV lines cited in each comment below.
# This list is deliberately the union of every tool this sweep corrected a
# false "not installed" claim about -- if a name is missing here, either it
# was never mis-claimed, or the sweep missed it (worth re-running the sweep
# if that surfaces later).
_EXPECTED_ON_PATH_IN_IMAGE = {
    "nec2++": "git-cloned and built from tmolteno/necpp v2.3.4",
    "openEMS": "built from source, PATH extended via ENV in the Dockerfile",
    "nf2ff": "ships from the same openEMS source tree as openEMS itself",
    "OpenParEM3D": "built from source, PATH extended via ENV in the Dockerfile",
    "gmsh": "apt-installed",
    "gerbv": "apt-installed",
    "ngspice": "apt-installed",
    "Xyce": "built from source, PATH extended via ENV in the Dockerfile",
    "qucsator_rf": "git-cloned and built from ra3xdh/qucsator_rf v1.0.7",
    "ElmerSolver": "git-cloned and built from ElmerCSC/elmerfem release-26.2.1",
    "ElmerGrid": "git-cloned and built from ElmerCSC/elmerfem release-26.2.1",
    "palace": "git-cloned and built from awslabs/palace v0.17.0",
    "FreeCADCmd": "freecad-maintainers PPA, symlinked from lowercase freecadcmd",
}

# Genuinely absent, even inside the built image -- deliberately, per each
# tool's own Dockerfile comment or pyproject.toml extras-group comment
# (ADR-0012 for hfss; LTspice is Windows-only freeware). NOT part of this
# sweep's corrections, and this test does not expect that to change.
_EXPECTED_GENUINELY_ABSENT_EVERYWHERE = {
    "pyaedt": "licence-confined to a real workstation with AEDT installed (ADR-0012)",
    "LTspice": "Windows-only proprietary freeware, not installable on this Linux image",
}


@pytest.mark.skipif(
    not _RUNNING_IN_A_CONTAINER,
    reason=(
        "no /.dockerenv marker -- this is a bare host or CI runner, not the "
        "built image, so every tool in _EXPECTED_ON_PATH_IN_IMAGE is "
        "legitimately absent here too (issue #480: 'absent on a bare host' "
        "is the honest claim outside the container, not 'not installed')"
    ),
)
class TestToolsExpectedOnPathInsideTheImage:
    @pytest.mark.parametrize("tool_name", sorted(_EXPECTED_ON_PATH_IN_IMAGE))
    def test_tool_is_on_path(self, tool_name):
        built_from = _EXPECTED_ON_PATH_IN_IMAGE[tool_name]
        assert shutil.which(tool_name) is not None, (
            f"{tool_name!r} was expected on PATH inside the built image "
            f"({built_from}), per issue #480's own verification table, but "
            f"shutil.which found nothing -- either the Dockerfile changed "
            f"and no longer installs it, or a docstring/doc claim needs to "
            f"be corrected back the other way"
        )


class TestToolsExpectedGenuinelyAbsent:
    """No skip needed -- these are absent everywhere, container or not, so
    the assertion holds regardless of where this test runs."""

    def test_pyaedt_is_not_importable(self):
        try:
            import pyaedt  # noqa: F401
        except ImportError:
            return
        pytest.fail(
            "pyaedt imported successfully -- simulation/hfss.py's own "
            "'NOT installed in this environment' caveat needs re-checking "
            "against this new fact, not left as a stale claim (issue #480)"
        )

    def test_ltspice_binary_is_absent(self):
        assert shutil.which("LTspice") is None, (
            "an 'LTspice' binary was found on PATH -- pyproject.toml's ltspice "
            "extra and its own comment ('LTspice is Windows freeware and is "
            "not in this image') need re-checking against this new fact "
            "(issue #480)"
        )
