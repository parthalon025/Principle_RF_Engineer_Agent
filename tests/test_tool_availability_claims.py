"""A consistency check between what this repo CLAIMS about tool availability
(in docstrings, comments, and docs/tools/*.md -- see issue #480's sweep) and
what is actually on PATH inside the built image, so a future drift there
can be checked mechanically instead of by hand the way issue #480 itself
had to be.

THE FOUR-CASE FRAMEWORK issue #480 established (its own words): a tool
adapter's "not installed" caveat can mean any of (1) the binary is genuinely
absent everywhere; (2) present but not on PATH; (3) present and on PATH but
its Python bindings aren't importable from the app interpreter; (4) present,
on PATH, and one of its code paths is broken. This test covers case 1 vs
"present in this project's own Docker image, absent on a bare host" only --
the shape every corrected site in this sweep actually needed. It is NOT a
functional check that any solver actually runs correctly (that is each
adapter's own fake-executable test suite); it only checks presence-on-PATH
(or, for gprMax, importability from its own dedicated interpreter), the
same fact the corrected docstrings now state.

WHY A CONTAINER MARKER, NOT A HOSTNAME OR ENV VAR THIS REPO INVENTED. Docker
creates `/.dockerenv` inside every container by convention (unrelated to
this repo, so it needs no Dockerfile change to rely on) -- a reliable signal
that this test is running where the Dockerfile's RUN steps actually
executed, as opposed to a bare checkout (this sandbox) or CI.

HONEST GAP THIS TEST DOES NOT CLOSE: `.github/workflows/ci.yml` runs pytest
directly on the GitHub Actions runner host, not inside this project's own
Docker image (only Postgres runs as a service container there) -- so
`TestToolsExpectedOnPathInsideTheImage` skips on every automated CI run
today, and nothing currently runs it for real. It only executes, and only
then actually checks anything, when a person runs the test suite by hand
inside a `docker run`/`docker compose run app pytest` invocation of the
built image. That is a real, disclosed gap, not a silently-assumed one:
wiring a container-based CI job that would actually exercise this class is
future work this ticket does not attempt. Until then, this class documents
the expected shape and is ready the moment such a job exists; it is not
"drift caught mechanically" today, only "drift catchable mechanically, by
hand, right now."

WHY pyaedt/spicelib ARE NOT RE-CHECKED HERE. `tests/test_hfss.py`'s own
`test_pyaedt_is_genuinely_not_installed_in_this_environment` already asserts
pyaedt's absence (via `import ansys.aedt.core`, its real importable module
name) -- duplicating that here would be two assertions of the same fact that
could silently drift apart, and on the one place pyaedt is EXPECTED to be
present (a real, licensed HFSS workstation with `uv sync --extra hfss` run,
per ADR-0012), a second, unconditional "absent" assertion here would be
actively wrong, not just redundant. `tests/test_ltspice.py` already gates
its own suite on `pytest.importorskip("spicelib")` rather than asserting
absence outright, for the same reason (a workstation with `--extra ltspice`
is a legitimate, supported target). Neither genuinely-absent-by-default
tool needs a duplicate assertion in this file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_RUNNING_IN_A_CONTAINER = Path("/.dockerenv").exists()

# Every one of these is confirmed, in the built image, on PATH via a direct
# citation in the Dockerfile itself (not just this sweep's own prose) --
# see each corrected adapter's own "HONEST CAVEAT" docstring for the
# specific Dockerfile line. This list is deliberately the union of every
# tool this sweep corrected a false "not installed" claim about via a
# `shutil.which`-checkable binary name -- if a name is missing here, either
# it was never mis-claimed, it needs a different check shape (gprMax,
# below), or the sweep missed it.
_EXPECTED_ON_PATH_IN_IMAGE = {
    "nec2++": "git-cloned and built from tmolteno/necpp v2.3.4",
    "openEMS": "built from source (v0.0.36), PATH extended via ENV in the Dockerfile",
    "OpenParEM3D": "built from source, PATH extended via ENV in the Dockerfile",
    "gmsh": "apt-installed (version unpinned)",
    "gerbv": "apt-installed (version unpinned)",
    "ngspice": "apt-installed (version unpinned)",
    "Xyce": "built from source (Release-7.10.0), PATH extended via ENV in the Dockerfile",
    "qucsator_rf": "git-cloned and built from ra3xdh/qucsator_rf v1.0.7",
    "ElmerSolver": "git-cloned and built from ElmerCSC/elmerfem release-26.2.1",
    "ElmerGrid": "git-cloned and built from ElmerCSC/elmerfem release-26.2.1",
    "palace": "git-cloned and built from awslabs/palace v0.17.0",
    "FreeCADCmd": "freecad-maintainers PPA (version unpinned), symlinked from lowercase freecadcmd",
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
            f"({built_from}), but shutil.which found nothing -- either the "
            f"Dockerfile changed and no longer installs it, or a "
            f"docstring/doc claim needs to be corrected back the other way"
        )

    def test_nf2ff_is_on_path(self):
        # A separate executable from `openEMS` itself, living in the same
        # openEMS submodule source tree the Dockerfile's build targets --
        # but unlike the entries above, the Dockerfile has no explicit
        # post-build `nf2ff --help`-style check confirming it specifically
        # (see simulation/openems.py's own caveat), so this assertion is
        # this test's own first real confirmation, not a re-statement of
        # something the Dockerfile already verifies at build time.
        assert shutil.which("nf2ff") is not None, (
            "'nf2ff' was expected on PATH inside the built image (same "
            "openEMS submodule source tree as openEMS itself), but "
            "shutil.which found nothing -- simulation/openems.py's own "
            "caveat about this needs re-checking"
        )

    def test_gprmax_module_is_importable_from_its_own_interpreter(self):
        # gprMax is a Python module installed into a dedicated venv
        # (`/opt/gprmax-venv`, `GPRMAX_PYTHON` env var), not a standalone
        # binary on PATH -- `shutil.which("gprMax")` would never find it
        # even inside the image, so this needs its own check shape rather
        # than folding into _EXPECTED_ON_PATH_IN_IMAGE above.
        gprmax_python = os.environ.get("GPRMAX_PYTHON")
        assert gprmax_python, (
            "GPRMAX_PYTHON is unset even inside the built image -- the "
            "Dockerfile's own `ENV GPRMAX_PYTHON=...` line needs "
            "re-checking against this new fact"
        )
        result = subprocess.run(
            [gprmax_python, "-c", "import gprMax"],
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"'import gprMax' failed under {gprmax_python!r} inside the "
            f"built image -- simulation/gprmax.py's own caveat about "
            f"this needs re-checking: {result.stderr.decode(errors='replace')}"
        )
