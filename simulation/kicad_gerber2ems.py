"""KiCad PCB -> gerber2ems -> openEMS signal-integrity simulation pipeline
(issue #65).

WHAT THIS MODULE IS: a PARALLEL geometry-input path, alongside
simulation/nec2pp.py and simulation/openems.py, specific to real,
as-laid-out KiCad PCB copper geometry -- trace impedance and via/stackup
S-parameters for a planar PCB-etched antenna feed network or any other
signal-integrity trace, NOT a hand-modeled wire/box geometry dict. It is
explicitly scoped to PCB signal-integrity results only: gerber2ems has no
far-field/gain capability at all (confirmed against its own source below),
so unlike simulation/openems.py this module does not even carry a stubbed
"far_field" key -- there is nothing to honestly stub.

WHY THIS HAS NO DEPENDENCY ON simulation/openems.py's generate_openems_xml()/
geometry-dict schema (verified, not assumed, per this ticket's own
instruction): gerber2ems drives openEMS through its OWN Python interface
(constructing FDTD-XML geometry itself from Gerber/drill/stackup files via
its `Simulation` class in src/gerber2ems/simulation.py, and invoking
openEMS's Python bindings directly), not through any file or API this repo
defines. This module therefore treats gerber2ems as an independent,
subprocess-invoked tool (its own `simulation.json` config schema, verified
below) exactly the way simulation/nec2pp.py treats nec2++ -- not as a
consumer of this repo's own geometry schema.

SOURCES CONSULTED (primary; all fetched directly from the upstream
antmicro/gerber2ems and kicad/code/kicad-python GitLab/GitHub repositories
during implementation -- see the per-fact citations below. Accessed
2026-09-02):

  GERBER2EMS (github.com/antmicro/gerber2ems, Apache-2.0 -- see LICENSE
  file, "Apache License, Version 2.0"):
  - CLI contract: `src/gerber2ems/main.py`'s `parse_arguments()` --
    `-a/--all` runs geometry+simulate+postprocess in one invocation;
    `-c/--config` overrides the config path (default `./simulation.json`,
    `DEFAULT_CONFIG_PATH` in `constants.py`); there is NO flag for the
    Gerber/drill/stackup input directory -- `src/gerber2ems/importer.py`
    hardcodes `Path.cwd() / "fab"` for every input file it reads (gerbers:
    `fab.glob("*_Cu.gbr")`/`fab.glob("*Edge_Cuts.gbr")`; drill: any file
    under `fab/` whose name contains `-PTH.drl`; stackup:
    `fab/stackup.json`; port positions: `fab.glob("*pos.csv")`). This is
    why KicadGerber2emsSimulator.run() below passes `cwd=workdir` rather
    than any input-path CLI argument.
  - Output layout: `src/gerber2ems/constants.py` -- `BASE_DIR = "ems"`,
    with `geometry/`, `simulation/`, `results/` subdirectories, all
    relative to gerber2ems's own cwd (same `workdir`).
  - `simulation.json` config schema: `src/gerber2ems/config.py`'s `_Config`
    dataclass (pyserde) -- `format_version` (must match
    `CONFIG_FORMAT_VERSION = "1.2"`, `constants.py`, checked by
    `is_cfg_version_invalid()`), `frequency.start`/`.stop` (Hz, e.g.
    `Frequency.stop` defaults to 6e9), `max_steps`, `pixel_size`,
    `via.plating_thickness`/`.filling_epsilon`, `grid.*`, `ports` (each:
    `width`/`length` in MICROMETERS -- `PortConfig.width` default 200,
    `.length` default 1000 -- `impedance`, `layer`, `plane`, `excite`),
    `traces` (single-ended: `start`/`stop` port indices), and
    `differential_pairs` (`start_p`/`stop_p`/`start_n`/`stop_n`). VERIFIED
    against a real, checked-in example
    (`examples/differential/simulation.json`), not just the dataclass
    definition. When `ports` is omitted/empty, `get_cfg_json()` in the same
    file auto-derives ports from any `SPn`-named ("Simulation_Port"
    footprint) rows in the exported `fab/*pos.csv` -- see
    export_kicad_fab_assets's docstring for the PCB-design-side
    precondition this relies on.
  - `stackup.json` schema: same `config.py`'s `LayerConfig.__init__` --
    reads `name`/`type`/`thickness`/`epsilon` (only `material`/
    `lossTangent` are carried through by callers, not read by LayerConfig
    itself); `parse_kind()` maps `type in ("core", "prepreg")` ->
    `LayerKind.SUBSTRATE` and `type == "copper"` -> `LayerKind.METAL`
    (anything else, e.g. "Top Solder Mask", -> `LayerKind.OTHER`, silently
    dropped by `Config.load_stackup()`) -- so "core" and "prepreg" are
    handled IDENTICALLY by gerber2ems, and any non-copper/core/prepreg
    `type` string is simply ignored. For a METAL (copper) layer,
    `self.file = config["name"].replace(".", "_")` is how gerber2ems maps
    a stackup entry to its expected Gerber filename (e.g. stackup "name"
    "F.Cu" -> expected substring "F_Cu" in a `fab/*_Cu.gbr` filename) --
    this is why extract_kicad_stackup() below uses KiCad's own dotted
    canonical layer names ("F.Cu", "In1.Cu", ...) for copper entries.
    THICKNESS UNITS VERIFIED AS MILLIMETERS (not micrometers -- an earlier
    pass of this research misread a paraphrased summary; corrected against
    the real checked-in example): `examples/differential/fab/stackup.json`
    shows `"F.Cu"` `"thickness": 0.035` (standard 1oz/35um copper = 0.035
    mm) and a `"core"` dielectric `"thickness": 0.12`. `STACKUP_FORMAT_
    VERSION = "1.0"` (`constants.py`).
  - Postprocessing output: `src/gerber2ems/postprocess.py`'s
    `Postprocesor.save_port_to_file()` writes one `Port_<excited-port>_
    data.csv` per excited port into the results directory (default
    `ems/results/`, i.e. `RESULTS_DIR` unless `-o` overrides it -- this
    module never passes `-o`, so it always reads the default), header
    `"Frequency [MHz],|S<j>-<i>| [-],...,Arg(S<j>-<i>) [rad],...,Delay
    <i>><j> [s],...,|Z<i>| [Ohm],Arg(Z<i>) [rad]"` (one `|S...|`/`Arg(S...)`/
    `Delay` triad of columns per port `j`, for the file's own excited port
    `i`), rows written via `np.savetxt(..., fmt="%e", delimiter=", ")`.
    HONEST CAVEAT: only the WRITER source was read -- no real gerber2ems
    run's actual `Port_N_data.csv` output was available to inspect (the
    repo's `examples/` directory ships only simulation *inputs*), so
    parse_gerber2ems_port_csv() below is built to the letter of this
    source, not cross-checked against a real results file.
  - Package/entry point: `pyproject.toml` -- `name = "gerber2ems"`,
    `scripts = {gerber2ems = "gerber2ems.main:main", ...}`. NOT published
    to PyPI (confirmed: `https://pypi.org/pypi/gerber2ems/json` -> 404) --
    installed from source/git, same "manual tool" category as NEC2++/
    openEMS themselves; documented in README.md's Optional-tools list,
    not a pyproject.toml extra (per this repo's CLAUDE.md convention).

  KICAD-PYTHON (gitlab.com/kicad/code/kicad-python, PyPI distribution
  "kicad-python" MIT-licensed -- `pyproject.toml`'s `license = "MIT"`,
  corroborated by PyPI's own `info.license_expression: "MIT"` -- importable
  as `kipy`, NOT `kicad_python`; `pyproject.toml`'s
  `[tool.poetry] packages = [{include = "kipy"}]`):
  - `kipy.KiCad(headless=True, file_path=..., kicad_cli_path=...,
    timeout_ms=...)`: `kipy/kicad.py` -- headless mode "Start[s] and
    connect[s] to a headless `kicad-cli api-server` instance" pre-loaded
    with the given file; `.get_board() -> Board` ("Retrieves a reference to
    the PCB open in KiCad, if one exists"); real-file usage pattern (`with
    KiCad(headless=True, kicad_cli_path=..., file_path=...) as kicad:`)
    confirmed against the package's own checked-in
    `examples/headless.py`. This is why this module scripts against
    kicad-python's IPC API (KiCad 9.0+, "5 - Production/Stable" on PyPI)
    rather than the legacy `pcbnew` SWIG bindings -- current as of this
    research pass: SWIG bindings are deprecated as of KiCad 9.0 and slated
    for removal in KiCad 11 (kicad.org dev docs), while kicad-python's IPC
    API had its "first formal release" in April 2026 against KiCad 10.0.0
    (stable as of this research date). kicad-cli (the separate KiCad
    command-line tool) is a REQUIRED system-level dependency this headless
    mode shells out to internally -- not invoked directly by this module.
  - `Board.export_gerbers(output_path, plot_settings=..., ...,
    use_protel_file_extensions=True, ...) -> JobResult`,
    `Board.export_drill(output_path, format=DrillFormat.DF_EXCELLON) ->
    JobResult`, `Board.export_position(output_path, settings=...) ->
    JobResult`, `Board.get_stackup() -> BoardStackup`,
    `Board.get_enabled_layers() -> list[BoardLayer]`: `kipy/board.py`,
    every signature fetched and read directly (not summarized). CRITICAL,
    independently-caught detail: `export_gerbers`'s OWN Python-level
    default is `use_protel_file_extensions=True` (Protel-style `.gtl`/
    `.gbl`/... extensions) -- this module MUST pass
    `use_protel_file_extensions=False` explicitly, or the exported
    filenames would never match gerber2ems's hardcoded `*_Cu.gbr`/
    `*Edge_Cuts.gbr` glob patterns above. `export_position`'s exact-target-
    file-path usage (`board.export_position(str(out /
    "<name>-position.csv"), settings=position)` with
    `position.single_file = True`) is copied from the package's own
    checked-in `examples/jobs.py`, which also confirms
    `from kipy.board import DrillFormat, GerberPrecision, PositionFormat,
    PositionSide, Units` and `from kipy.board_jobs import PlotSettings,
    PositionExportSettings` as the real import paths.
  - `PositionFormat.PF_CSV = 2`, `DrillFormat.DF_EXCELLON = 1`:
    `api/proto/board/board_jobs.proto` in the main `kicad/code/kicad`
    repository (the source these kicad-python enums are generated from),
    fetched and read directly.
  - `BoardStackupLayer.thickness` (int, NANOMETERS -- `self._proto.
    thickness.value_nm`), `.layer` (BoardLayer, `BL_UNDEFINED` for a
    dielectric entry), `.enabled`, `.type`
    (`board_pb2.BoardStackupLayerType`), `.dielectric ->
    Optional[BoardStackupDielectricLayer]` (whose `.layers` is a
    `List[BoardStackupDielectricProperties]`, each with `.epsilon_r`,
    `.loss_tangent`, `.material_name`, `.thickness`): `kipy/board.py`,
    fetched and read directly. `BSLT_COPPER`/`BSLT_DIELECTRIC` enum member
    names (on `kipy.proto.board.board_pb2.BoardStackupLayerType`,
    accessed exactly as `board.py` itself does internally) confirmed via
    `board_stackup.cpp`'s `BOARD_STACKUP::Serialize()` in the main KiCad
    repo, which maps `BS_ITEM_TYPE_COPPER`/`BS_ITEM_TYPE_DIELECTRIC` (C++)
    to these two protobuf names via `ToProtoEnum<...>`.
  - `kipy.util.board_layer.canonical_name(layer) -> str` (e.g.
    `BL_F_Cu` -> `"F.Cu"`, `BL_In1_Cu` -> `"In1.Cu"`) and `.is_copper_
    layer(layer) -> bool`: `kipy/util/board_layer.py`, fetched and read
    directly, matches gerber2ems's own dotted stackup "name" convention
    exactly (see above).
  - `BoardLayer.BL_F_Cu = 3`, `.BL_In1_Cu = 4`, `.BL_B_Cu = 34`,
    `.BL_Edge_Cuts = 47`: `api/proto/board/board_types.proto` in the main
    KiCad repo, fetched and read directly.
  - `JobResult.output_paths -> list[str]`, `.succeeded -> bool`,
    `.message -> str`: `kipy/board_jobs.py`, fetched and read directly --
    used by export_kicad_fab_assets() below to discover the REAL file(s)
    KiCad wrote, rather than assuming an exact filename.

  KICAD (the application/kicad-cli itself, GPL-3.0-or-later): kicad.org's
  own "Licenses" page (kicad.org/about/licenses/) -- "The majority of
  KiCad's source code is developed and distributed under the GNU General
  Public License (GPL) version 3 or greater". A manual/system install, not
  pip-installable -- documented in README.md's Optional-tools list.
  - `kicad-cli pcb drc` (issue #272): CLI options `--format`, `--output`,
    `--severity-*`, `--exit-code-violations` and its own documented
    exit-code-0-vs-5 contract ("The exit code is 0 if no violations are
    found, and 5 if any violations are found") --
    https://docs.kicad.org/9.0/en/cli/cli.html, fetched directly. The DRC
    JSON report shape it writes (`violations[]` with
    `type`/`severity`/`description`/`excluded`/`items`; `severity` enum
    "error"/"warning") is KiCad's own published schema,
    https://schemas.kicad.org/drc.v1.json (redirects to
    https://gitlab.com/kicad/code/kicad/-/raw/master/resources/schemas/drc.v1.json),
    also fetched directly. See run_kicad_drc()/parse_kicad_drc_report()
    below, and docs/tools/kicad-gerber2ems.md's own [11]/[12] citations to
    the same two sources.

  GERBV (the external rasterizer gerber2ems shells out to internally for
  Gerber-to-PNG conversion, GPL-2.0): confirmed via the maintained fork's
  own README ("Gerbv and all associated files are placed under the GNU
  Public License (GPL) version 2.0"). A manual/system install (not
  pip-installable) -- documented in README.md's Optional-tools list.

HONEST CAVEATS (matching the discipline in simulation/nec2pp.py's and
simulation/openems.py's own module headers):
  1. NONE of gerber2ems, kicad-python, kicad-cli, gerbv, or a real openEMS
     binary is installed in this environment. Every fact above was
     verified by reading each project's own primary source directly (not
     inferred, not guessed) -- but this module's actual subprocess/IPC
     invocations have NEVER been run end-to-end against the real tools.
     Treat any result as unverified end-to-end until it has been.
  2. kicad-python's `Board.export_drill()` (as of this pass -- kicad-python
     0.8.0/KiCad 10) exposes only `output_path`/`format`, NOT the separate
     plated/non-plated-hole `ExcellonFormatOptions` its own underlying
     `RunBoardJobExportDrill` proto message supports. gerber2ems hardcodes
     an expectation of a PLATED-ONLY drill file named `*-PTH.drl`. This
     module cannot force that distinction through kicad-python's current
     wrapper, so export_kicad_fab_assets() below renames whatever single
     combined drill file KiCad produces to carry the `-PTH.drl` suffix --
     correct only if every hole on the board is plated. Flagged in that
     function's own return value (`warnings`), never silently assumed.
  3. gerber2ems's own port-position workflow REQUIRES the KiCad PCB design
     to already place "Simulation_Port"-valued footprints (reference
     designators `SP1`, `SP2`, ...) at every trace endpoint of interest --
     confirmed from `config.py`'s `get_ports_from_file()`
     (`"Simulation_Port" in row[2]`) and a real checked-in example CSV
     (`examples/differential/fab/*-top-pos.csv`, rows literally
     `"SP1","Simulation_Port","Simulation_Port",...`). This is a
     PCB-design-time precondition this module cannot synthesize -- it is
     not a limitation of this module's code, it is how gerber2ems itself
     works.
"""

import csv
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError

_STACKUP_FORMAT_VERSION = "1.0"  # gerber2ems's own STACKUP_FORMAT_VERSION
# (src/gerber2ems/constants.py) -- see module docstring citation.
_CONFIG_FORMAT_VERSION = "1.2"  # gerber2ems's own CONFIG_FORMAT_VERSION
# (src/gerber2ems/constants.py), checked by its own is_cfg_version_invalid()
# -- see module docstring citation.
_KICAD_CLI_DRC_EXIT_CODES_OK = (0, 5)  # kicad-cli's own documented
# `--exit-code-violations` contract for `pcb drc` (docs.kicad.org/9.0/en/
# cli/cli.html, see module docstring citation): 0 = no violations, 5 =
# violations found -- BOTH are successful DRC runs, not tool failures.


class KicadGerber2emsSimulator(Simulator):
    name = "gerber2ems"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("GERBER2EMS_BIN") or "gerber2ems"

    def run(self, job: dict) -> SimulationResult:
        workdir = Path(job["workdir"]).resolve()
        fab_dir = workdir / "fab"
        config_file = workdir / "simulation.json"
        if not fab_dir.is_dir():
            raise SimulatorError(
                f"{fab_dir} not found -- call export_kicad_fab_assets() (or "
                "run_kicad_gerber2ems_simulation, which does this for you) "
                "before KicadGerber2emsSimulator.run()"
            )
        if not config_file.is_file():
            raise SimulatorError(
                f"{config_file} not found -- call generate_gerber2ems_config() "
                "and write its result to workdir/'simulation.json' before "
                "KicadGerber2emsSimulator.run()"
            )

        # gerber2ems's own argparse contract (see module docstring citation
        # to its main.py): "-a" runs all three steps (geometry, simulate,
        # postprocess) in one invocation, reading `fab/` and `simulation.json`
        # relative to its OWN CWD -- there is no CLI flag for the fab/
        # directory itself, hence cwd=workdir below rather than an argument.
        timeout_s = int(job.get("timeout_s", 3600))
        try:
            completed = subprocess.run(
                [self.executable, "-a"],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"gerber2ems timed out after {timeout_s}s: {exc}") from exc
        if completed.returncode != 0:
            raise SimulatorError(
                f"gerber2ems failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-8000:], "stderr": completed.stderr[-4000:]},
        )


# ---------------------------------------------------------------------------
# kicad-python (kipy) IPC-API bundle -- gathered into one small injectable
# object so export_kicad_fab_assets()/extract_kicad_stackup() below can take
# either the REAL kipy imports (the default, used by
# run_kicad_gerber2ems_simulation for a real call) or a hand-written fake
# matching this same shape (tests/test_kicad_gerber2ems.py, no kicad-python
# install required) -- mirrors simulation/hfss.py's hfss_factory
# constructor-injection seam, applied to a module-level dependency bundle
# instead of one constructed client instance.
# ---------------------------------------------------------------------------


class _KipyBoardApi:
    def __init__(
        self,
        DrillFormat: Any,
        PositionFormat: Any,
        PlotSettings: Any,
        PositionExportSettings: Any,
        board_pb2: Any,
        canonical_name: Callable[[Any], str],
    ):
        self.DrillFormat = DrillFormat
        self.PositionFormat = PositionFormat
        self.PlotSettings = PlotSettings
        self.PositionExportSettings = PositionExportSettings
        self.board_pb2 = board_pb2
        self.canonical_name = canonical_name


def _real_kipy_board_api() -> _KipyBoardApi:
    """Guarded import of the kicad-python (kipy) names this module needs --
    deferred to inside this function since kicad-python (and a real KiCad/
    kicad-cli install to connect to) genuinely will not be present in most
    environments, including this one (see module docstring)."""
    try:
        from kipy.board import DrillFormat, PositionFormat
        from kipy.board_jobs import PlotSettings, PositionExportSettings
        from kipy.proto.board import board_pb2
        from kipy.util.board_layer import canonical_name
    except ImportError as exc:
        raise SimulatorError(
            "kicad-python is not installed. Install the optional 'kicad' "
            "dependency group, e.g. `uv sync --extra kicad` or "
            "`pip install '.[kicad]'` -- and see README.md's Optional-tools "
            "list for the separate KiCad application/kicad-cli install this "
            "IPC connection additionally requires."
        ) from exc
    return _KipyBoardApi(
        DrillFormat, PositionFormat, PlotSettings, PositionExportSettings, board_pb2, canonical_name
    )


def _real_connect_and_get_board(
    board_file: str, kicad_cli_path: str | None = None, timeout_ms: int = 60000
) -> tuple[Any, Any]:
    """Launch a headless `kicad-cli api-server` pre-loaded with `board_file`
    (see module docstring citation to kipy.KiCad(headless=True,
    file_path=...)) and return (kicad_connection, board). The caller OWNS
    kicad_connection and MUST call its .close() when done (stops the
    headless server) -- run_kicad_gerber2ems_simulation below always does
    this in a finally block."""
    try:
        from kipy import KiCad
    except ImportError as exc:
        raise SimulatorError(
            "kicad-python is not installed. Install the optional 'kicad' "
            "dependency group, e.g. `uv sync --extra kicad` or "
            "`pip install '.[kicad]'`."
        ) from exc

    kicad = KiCad(
        headless=True,
        file_path=str(board_file),
        kicad_cli_path=kicad_cli_path,
        timeout_ms=timeout_ms,
    )
    try:
        board = kicad.get_board()
    except Exception:
        kicad.close()
        raise
    if board is None:
        kicad.close()
        raise SimulatorError(
            f"KiCad headless server did not report a loaded board for {board_file!r}"
        )
    return kicad, board


def extract_kicad_stackup(board: Any, api: _KipyBoardApi | None = None) -> dict[str, Any]:
    """Translate a connected board's stackup (Board.get_stackup(), see
    module docstring citation) into gerber2ems's own stackup.json shape
    (format_version + layers with name/type/thickness(mm)/material/
    epsilon/lossTangent -- see module docstring citation to gerber2ems's
    own LayerConfig and a real checked-in example file this was verified
    against).

    `board` needs only `.get_stackup()`; `api` is the kicad-python IPC-API
    bundle (see _KipyBoardApi above) -- omit for a real call (the default
    does the real guarded kipy import), or pass a fake for tests.

    A dielectric stackup slot that is itself made of multiple sub-layers
    (BoardStackupDielectricLayer.layers, KiCad's own per-slot
    multi-material support) is collapsed to its FIRST sub-layer's
    material/epsilon/loss-tangent here -- gerber2ems's own stackup.json
    schema has no concept of multiple material zones within one dielectric
    slot either (LayerConfig reads a single "epsilon"/"material" key), so
    this is a real, honest simplification, not a silently-wrong one.
    """
    api = api or _real_kipy_board_api()
    board_pb2 = api.board_pb2

    layers_out: list[dict[str, Any]] = []
    dielectric_count = 0
    for entry in board.get_stackup().layers:
        if not entry.enabled:
            continue
        thickness_mm = entry.thickness / 1_000_000.0  # kipy reports nanometers
        layer_dict: dict[str, Any] = {
            "color": None,
            "thickness": thickness_mm,
            "material": None,
            "epsilon": None,
            "lossTangent": None,
        }
        if entry.type == board_pb2.BoardStackupLayerType.BSLT_COPPER:
            layer_dict["name"] = api.canonical_name(entry.layer)
            layer_dict["type"] = "copper"
        elif entry.type == board_pb2.BoardStackupLayerType.BSLT_DIELECTRIC:
            dielectric_count += 1
            layer_dict["name"] = f"dielectric_{dielectric_count}"
            # "core"/"prepreg" are handled identically by gerber2ems's own
            # LayerConfig.parse_kind() (see module docstring) -- collapsing
            # KiCad's finer core/prepreg distinction is therefore lossless
            # for gerber2ems's own purposes.
            layer_dict["type"] = "core"
            dielectric = entry.dielectric
            sub_layers = dielectric.layers if dielectric is not None else []
            if sub_layers:
                sub = sub_layers[0]
                layer_dict["material"] = sub.material_name or None
                layer_dict["epsilon"] = sub.epsilon_r
                layer_dict["lossTangent"] = sub.loss_tangent
        else:
            # Silkscreen/mask/paste/etc -- gerber2ems's own LayerConfig.
            # parse_kind() falls through to LayerKind.OTHER for anything
            # that isn't literally "copper"/"core"/"prepreg", and
            # Config.load_stackup() filters those out entirely, so the
            # exact name/type recorded here is never read by gerber2ems.
            layer_dict["name"] = api.canonical_name(entry.layer) if entry.layer else "other"
            layer_dict["type"] = "other"
        layers_out.append(layer_dict)

    return {"format_version": _STACKUP_FORMAT_VERSION, "layers": layers_out}


def export_kicad_fab_assets(
    board: Any, fab_dir: str | Path, api: _KipyBoardApi | None = None
) -> dict[str, Any]:
    """Export the Gerber/drill/position fileset plus a translated
    stackup.json into `fab_dir` -- gerber2ems's own hardcoded `./fab`
    directory name relative to its run cwd (see module docstring citation
    to gerber2ems's own importer.py).

    `board` is an already-connected kipy.board.Board (or a fake matching
    the subset of its API used here: `.name`, `.get_enabled_layers()`,
    `.export_gerbers()`, `.export_drill()`, `.export_position()`,
    `.get_stackup()`) -- a seam parameter so this function is testable
    without a real KiCad/kicad-cli install; see
    _real_connect_and_get_board/run_kicad_gerber2ems_simulation for the
    real connection this is normally called with, and
    tests/test_kicad_gerber2ems.py for the fake.

    REQUIRES the board to already carry "Simulation_Port"-valued
    footprints (reference designators SP1, SP2, ...) at every trace
    endpoint of interest -- see module docstring's honest-caveat #3. A
    board without them still exports fine; gerber2ems's own
    auto-port-discovery (triggered whenever the `config` passed to
    generate_gerber2ems_config omits "ports") then simply finds none.

    Returns a dict of the resulting file paths plus any honestly-flagged
    `warnings` (see module docstring's honest-caveat #2 on the drill-file
    plated-only assumption).
    """
    api = api or _real_kipy_board_api()
    fab_dir = Path(fab_dir)
    fab_dir.mkdir(parents=True, exist_ok=True)
    board_stem = Path(board.name).stem or "board"
    warnings: list[str] = []

    plot_settings = api.PlotSettings()
    plot_settings.layers = list(board.get_enabled_layers())
    gerber_result = board.export_gerbers(
        str(fab_dir),
        plot_settings=plot_settings,
        # use_protel_file_extensions=False is REQUIRED -- see module
        # docstring citation: kipy's own Python-level default for this
        # parameter is True (Protel-style .gtl/.gbl/... extensions), which
        # would not match gerber2ems's hardcoded "*_Cu.gbr"/"*Edge_Cuts.gbr"
        # glob patterns.
        use_protel_file_extensions=False,
    )
    if not gerber_result.succeeded:
        raise SimulatorError(f"KiCad Gerber export failed: {gerber_result.message!r}")
    gerber_paths = list(gerber_result.output_paths)
    if not any(p.endswith("_Cu.gbr") for p in gerber_paths):
        raise SimulatorError(
            f"KiCad Gerber export produced no '*_Cu.gbr' copper-layer file "
            f"in {fab_dir} (got: {[Path(p).name for p in gerber_paths]}) -- "
            "gerber2ems has no copper layer to simulate"
        )
    if not any(p.endswith("Edge_Cuts.gbr") for p in gerber_paths):
        raise SimulatorError(
            f"KiCad Gerber export produced no '*Edge_Cuts.gbr' board-outline "
            f"file in {fab_dir} -- gerber2ems needs it to size the "
            "simulation domain"
        )

    drill_result = board.export_drill(str(fab_dir), format=api.DrillFormat.DF_EXCELLON)
    if not drill_result.succeeded:
        raise SimulatorError(f"KiCad drill export failed: {drill_result.message!r}")
    drill_paths = [Path(p) for p in drill_result.output_paths]
    if not drill_paths:
        raise SimulatorError(f"KiCad drill export produced no output file in {fab_dir}")
    pth_drill = next((p for p in drill_paths if "-PTH.drl" in p.name), None)
    if pth_drill is None:
        # See module docstring's honest-caveat #2: kipy's export_drill()
        # does not (as of this pass) expose a plated/non-plated-hole split,
        # so this renames the one combined drill file KiCad produced --
        # correct only if every hole on this board is plated.
        original = drill_paths[0]
        pth_drill = original.with_name(original.stem + "-PTH.drl")
        shutil.move(str(original), str(pth_drill))
        warnings.append(
            f"renamed KiCad's combined drill file {original.name!r} to "
            f"{pth_drill.name!r} to match gerber2ems's '*-PTH.drl' import "
            "pattern -- ASSUMES every hole on this board is plated; "
            "kicad-python's export_drill() does not yet expose a separate "
            "plated/non-plated Excellon export (see module docstring)"
        )

    position_settings = api.PositionExportSettings()
    position_settings.format = api.PositionFormat.PF_CSV
    position_settings.single_file = True
    pos_csv_path = fab_dir / f"{board_stem}-pos.csv"
    position_result = board.export_position(str(pos_csv_path), settings=position_settings)
    if not position_result.succeeded:
        raise SimulatorError(f"KiCad position-file export failed: {position_result.message!r}")

    stackup = extract_kicad_stackup(board, api=api)
    stackup_path = fab_dir / "stackup.json"
    stackup_path.write_text(json.dumps(stackup, indent=2))

    return {
        "fab_dir": str(fab_dir),
        "gerber_files": gerber_paths,
        "drill_file": str(pth_drill),
        "position_file": str(pos_csv_path),
        "stackup_file": str(stackup_path),
        "warnings": warnings,
    }


def generate_gerber2ems_config(config: dict[str, Any]) -> dict[str, Any]:
    """Build a gerber2ems `simulation.json` dict from `config`, in
    gerber2ems's OWN schema -- this module does not invent a translation
    layer here (see module docstring: gerber2ems drives openEMS through
    its own Python interface with its own config format, not this repo's
    generate_openems_xml() geometry-dict schema).

    `config` shape (gerber2ems's own src/gerber2ems/config.py `_Config`
    dataclass, see module docstring citation) -- only `frequency` is
    required; every other key is optional and passed through unchanged,
    letting gerber2ems's own config loader apply its documented defaults
    (grid pitch/margins, max_steps, pixel_size, via plating). An empty/
    omitted `ports` list is a REAL, deliberate option -- it triggers
    gerber2ems's own auto-port-discovery from the exported `*pos.csv`
    SP<n>-named footprints (see export_kicad_fab_assets's own docstring):
        {
          "frequency": {"start": float_hz, "stop": float_hz},  # REQUIRED
          "max_steps": int,                     # optional
          "pixel_size": float,                  # optional, micrometers
          "via": {"plating_thickness": float, "filling_epsilon": float},
          "grid": {...},                        # optional, gerber2ems's own shape
          "ports": [{"width":.., "length":.., "impedance":.., "layer":..,
                      "plane":.., "excite":.., "name": str}, ...],
          "traces": [{"start":.., "stop":.., "name":..}, ...],
          "differential_pairs": [{"start_p":.., "stop_p":.., "start_n":..,
                                    "stop_n":.., "name":..}, ...],
        }
    Port/trace `width`/`length` are in MICROMETERS (gerber2ems's own
    PortConfig field defaults, width=200/length=1000); `frequency` is in
    Hz (gerber2ems's own Frequency dataclass, default 1e6-6e9).
    """
    frequency = config.get("frequency")
    if not frequency or "start" not in frequency or "stop" not in frequency:
        raise ValueError(
            "config['frequency'] = {'start': hz, 'stop': hz} is required "
            "(gerber2ems's own Frequency config has no repo-side default)"
        )

    cfg: dict[str, Any] = {"format_version": _CONFIG_FORMAT_VERSION}
    passthrough_keys = (
        "frequency",
        "max_steps",
        "pixel_size",
        "via",
        "grid",
        "ports",
        "traces",
        "differential_pairs",
    )
    for key in passthrough_keys:
        if key in config:
            cfg[key] = config[key]
    return cfg


# Matches gerber2ems's own Postprocesor.save_port_to_file() column labels
# (src/gerber2ems/postprocess.py) -- see module docstring citation and its
# honest caveat that this was verified against the WRITER source only, not
# a real results file.
_S_MAG_RE = re.compile(r"^\|S(\d+)-\d+\|")
_S_ARG_RE = re.compile(r"^Arg\(S(\d+)-\d+\)")
_DELAY_RE = re.compile(r"^Delay \d+>(\d+)")
_PORT_CSV_RE = re.compile(r"Port_(\d+)_data\.csv$")


def parse_gerber2ems_port_csv(path: str | Path) -> dict[str, Any]:
    """Parse one gerber2ems `Port_<excited>_data.csv` postprocessing result
    file into a structured, frequency-indexed dict: `frequency_hz`,
    `s_parameters` (`{"S<output><excited>": [[re, im], ...], ...}`, one
    entry per output port column found in the header),
    `trace_delay_s` (`{"<excited>><output>": [seconds, ...], ...}`), and
    `impedance_ohms` (`[[re, im], ...]`, the excited port's own
    driving-point impedance). See module docstring citation and honest
    caveat.
    """
    path = Path(path)
    match = _PORT_CSV_RE.search(path.name)
    excited_port = int(match.group(1)) if match else None

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]
        data_rows = [[float(v) for v in row] for row in reader if row]

    mag_idx: dict[int, int] = {}
    arg_idx: dict[int, int] = {}
    delay_idx: dict[int, int] = {}
    z_mag_col: int | None = None
    z_arg_col: int | None = None
    for col, label in enumerate(header):
        m = _S_MAG_RE.match(label)
        if m:
            mag_idx[int(m.group(1))] = col
            continue
        m = _S_ARG_RE.match(label)
        if m:
            arg_idx[int(m.group(1))] = col
            continue
        m = _DELAY_RE.match(label)
        if m:
            delay_idx[int(m.group(1))] = col
            continue
        if label.startswith("|Z"):
            z_mag_col = col
        elif label.startswith("Arg(Z"):
            z_arg_col = col

    frequency_hz = [row[0] * 1e6 for row in data_rows]

    s_parameters: dict[str, list[list[float]]] = {}
    for output_port, mag_col in mag_idx.items():
        arg_col = arg_idx.get(output_port)
        if arg_col is None:
            continue
        s_name = f"S{output_port}{excited_port}"
        s_parameters[s_name] = [
            [row[mag_col] * math.cos(row[arg_col]), row[mag_col] * math.sin(row[arg_col])]
            for row in data_rows
        ]

    trace_delay_s: dict[str, list[float]] = {
        f"{excited_port}>{output_port}": [row[col] for row in data_rows]
        for output_port, col in delay_idx.items()
    }

    impedance_ohms: list[list[float]] | None = None
    if z_mag_col is not None and z_arg_col is not None:
        impedance_ohms = [
            [row[z_mag_col] * math.cos(row[z_arg_col]), row[z_mag_col] * math.sin(row[z_arg_col])]
            for row in data_rows
        ]

    return {
        "excited_port": excited_port,
        "frequency_hz": frequency_hz,
        "s_parameters": s_parameters,
        "trace_delay_s": trace_delay_s,
        "impedance_ohms": impedance_ohms,
    }


def parse_gerber2ems_results(results_dir: str | Path) -> dict[str, Any]:
    """Aggregate every `Port_*_data.csv` gerber2ems wrote into `results_dir`
    (default `<workdir>/ems/results`, see module docstring citation) into
    `{"computed": bool, "ports": {"<excited_port>": {...}, ...}, "note":
    str | None}`. `computed=False` with an explanatory note (never
    fabricated numbers) when no such file exists -- e.g. the run didn't
    reach postprocessing, or (a fake test executable) doesn't emit them."""
    results_dir = Path(results_dir)
    csv_files = sorted(results_dir.glob("Port_*_data.csv")) if results_dir.is_dir() else []
    if not csv_files:
        return {
            "computed": False,
            "ports": {},
            "note": (
                f"No 'Port_*_data.csv' postprocessing result files found in "
                f"{results_dir} -- gerber2ems's own Postprocesor.save_to_"
                "file() (see module docstring citation) writes one per "
                "excited port after a full -a run reaches postprocessing; "
                "this can mean the run didn't get that far, no port's own "
                "S_ii was 'valid' per gerber2ems's own check, or (for a "
                "fake test executable) the fake script doesn't emit them."
            ),
        }
    parsed_ports = (parse_gerber2ems_port_csv(p) for p in csv_files)
    ports = {str(parsed["excited_port"]): parsed for parsed in parsed_ports}
    return {"computed": True, "ports": ports, "note": None}


def parse_kicad_drc_report(report: dict[str, Any]) -> dict[str, Any]:
    """Interpret one already-parsed KiCad DRC JSON report (the dict
    `json.loads()` of the file `kicad-cli pcb drc --format json --output
    <path> ...` writes -- see run_kicad_drc() below, which owns the
    subprocess invocation and file read) into `{"violation_count": int,
    "violations": [{"severity", "type", "description"}, ...]}`.

    Pure, no subprocess or file I/O -- this is the "interpret the tool's
    output" half of the run/parse split this module uses elsewhere
    (KicadGerber2emsSimulator.run() vs. parse_gerber2ems_port_csv()/
    parse_gerber2ems_results(); export_kicad_fab_assets() vs.
    extract_kicad_stackup()), so this filtering logic is directly
    unit-testable on a plain dict, with no fake executable required.

    The report shape (top-level `violations` array of
    `{type, severity, description, excluded, items}` objects) is KiCad's own
    published schema, https://schemas.kicad.org/drc.v1.json (fetched
    directly during this pass, confirmed against the underlying
    resources/schemas/drc.v1.json in the kicad/code/kicad source tree --
    see module docstring citation): `severity` is one of "error"/"warning";
    `excluded` (default false) marks a violation the PCB designer already
    reviewed in KiCad's own DRC dialog and told KiCad to stop reporting.
    This function filters `excluded` violations out of its returned
    `violations` list -- re-surfacing a violation a human already reviewed
    and dismissed on this exact board would not be load-bearing for the
    reader's go/no-go decision (CLAUDE.md: a warning must fire only when it
    would change the decision).
    """
    violations = [
        {
            "severity": v.get("severity"),
            "type": v.get("type"),
            "description": v.get("description"),
        }
        for v in report.get("violations", [])
        if not v.get("excluded", False)
    ]
    return {"violation_count": len(violations), "violations": violations}


def run_kicad_drc(
    board_file: str,
    workdir: str | Path,
    kicad_cli_path: str | None = None,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Run KiCad's own Design Rule Check against `board_file` via `kicad-cli
    pcb drc --format json --output <workdir>/drc_report.json
    --exit-code-violations <board_file>` (issue #272 -- the gap flagged in
    docs/tools/kicad-gerber2ems.md's "Capabilities not yet used here"
    section), then hand the resulting JSON violations report to
    parse_kicad_drc_report() (this function's own pure counterpart) to
    interpret.

    kicad-cli's own CLI reference (https://docs.kicad.org/9.0/en/cli/cli.html,
    fetched directly during this pass) documents `--exit-code-violations` as:
    "The exit code is 0 if no violations are found, and 5 if any violations
    are found" (`_KICAD_CLI_DRC_EXIT_CODES_OK` above) -- BOTH are successful
    DRC runs that still write the report; neither is a subprocess failure.
    Only any OTHER exit code (kicad-cli crashed, the board file is
    unreadable, kicad-cli itself is missing) is treated as one, raising
    SimulatorError -- mirroring KicadGerber2emsSimulator.run()'s own
    subprocess.run(..., cwd=..., capture_output=True, text=True, timeout=...,
    check=False) pattern.

    Returns `{"checked": True, "report_file": str, "violation_count": int,
    "violations": [{"severity", "type", "description"}, ...]}`. Per
    CLAUDE.md's "warn, never block": a nonzero `violation_count` is data for
    the caller to surface, never a reason for this function itself to raise
    -- see run_kicad_gerber2ems_simulation, which calls this BEFORE
    export_kicad_fab_assets()/KicadGerber2emsSimulator.run() and folds a
    nonzero count into that caller's own `warnings` list rather than
    aborting.

    `kicad_cli_path` mirrors run_kicad_gerber2ems_simulation's own
    same-named parameter (the same kicad-cli binary already required to
    launch the headless api-server for fab-asset export, see
    _real_connect_and_get_board) -- falls back to the `KICAD_CLI_BIN` env
    var, then the bare command "kicad-cli" on PATH, matching every other
    *_BIN convention in this repo's simulation/*.py adapters (e.g.
    GERBER2EMS_BIN above).
    """
    executable = kicad_cli_path or os.getenv("KICAD_CLI_BIN") or "kicad-cli"
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    report_file = workdir / "drc_report.json"

    args = [
        executable,
        "pcb",
        "drc",
        "--format",
        "json",
        "--output",
        str(report_file),
        "--exit-code-violations",
        str(board_file),
    ]
    try:
        completed = subprocess.run(
            args,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulatorError(f"kicad-cli pcb drc timed out after {timeout_s}s: {exc}") from exc
    except FileNotFoundError as exc:
        raise SimulatorError(
            f"kicad-cli was not found at {executable!r}. Pass kicad_cli_path=, set "
            "the KICAD_CLI_BIN env var, or install KiCad -- see README.md's "
            "Optional-tools list."
        ) from exc

    # See this function's own docstring: 0 and 5 are kicad-cli's own two
    # SUCCESSFUL --exit-code-violations outcomes (no violations / violations
    # found); anything else is a genuine tool failure, not a board finding.
    if completed.returncode not in _KICAD_CLI_DRC_EXIT_CODES_OK:
        raise SimulatorError(
            f"kicad-cli pcb drc failed ({completed.returncode}): {completed.stderr[-4000:]}"
        )
    if not report_file.is_file():
        raise SimulatorError(
            f"kicad-cli pcb drc exited {completed.returncode} but wrote no report to {report_file}"
        )

    report = json.loads(report_file.read_text())
    parsed = parse_kicad_drc_report(report)

    return {
        "checked": True,
        "report_file": str(report_file),
        "violation_count": parsed["violation_count"],
        "violations": parsed["violations"],
    }


def run_kicad_gerber2ems_simulation(
    board_file: str,
    config: dict[str, Any],
    workdir: str | None = None,
    timeout_s: int = 3600,
    executable: str | None = None,
    kicad_cli_path: str | None = None,
    connect_fn: Callable[..., tuple[Any, Any]] | None = None,
    kipy_api: _KipyBoardApi | None = None,
) -> dict[str, Any]:
    """Derive PCB signal-integrity simulation geometry from a real KiCad PCB
    design and run it through gerber2ems -> openEMS: connect to a headless
    KiCad instance loaded with `board_file`, export its Gerber/drill/
    position fileset plus a translated stackup.json
    (export_kicad_fab_assets), write gerber2ems's own `simulation.json`
    (generate_gerber2ems_config), run `gerber2ems -a` via
    KicadGerber2emsSimulator, and parse its per-port trace-impedance/
    S-parameter results (parse_gerber2ems_results).

    Returns a SIMULATED-provenance dict EXPLICITLY scoped to PCB
    signal-integrity results (trace impedance, via/stackup S-parameters)
    -- gerber2ems has no far-field/gain capability at all (see module
    docstring), so there is no "far_field" key here to stub, unlike
    simulation/openems.py's own result shape.

    Runs run_kicad_drc() FIRST, before connecting to KiCad for
    export_kicad_fab_assets()/before KicadGerber2emsSimulator.run() (issue
    #272) -- its structured result is folded into this dict's own "drc"
    key. Per CLAUDE.md's "warn, never block": a board with reported DRC
    violations still proceeds through export and simulation; the
    violations surface only as a human-readable entry in this dict's own
    top-level "warnings" list (mirroring export_kicad_fab_assets()'s own
    warnings: list[str] pattern for its plated-drill-file assumption,
    folded in alongside it here), never as a raised exception. A genuinely
    broken DRC invocation (kicad-cli missing/crashed -- see run_kicad_drc's
    own docstring on the difference) is NOT a board violation and still
    raises SimulatorError, before this function ever attempts to connect to
    KiCad.

    `connect_fn`/`kipy_api` are test-only injection seams (mirroring
    simulation/hfss.py's hfss_factory) -- omit both for a real call (the
    agent/MCP tool wiring always omits them, so a real invocation always
    goes through a real headless KiCad connection and real kicad-python
    imports).

    See this module's header comment for the full source-citation list and
    the three honest caveats: nothing here has been run against a real
    KiCad/kicad-cli/gerber2ems/openEMS install; the exported drill file is
    assumed fully plated (kicad-python does not yet expose that split);
    and port discovery depends on the PCB design already carrying
    "Simulation_Port"-valued footprints.
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="kicad_gerber2ems_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    fab_dir = work_dir / "fab"

    drc = run_kicad_drc(
        board_file, workdir=work_dir / "drc", kicad_cli_path=kicad_cli_path, timeout_s=timeout_s
    )

    connect = connect_fn or _real_connect_and_get_board
    kicad_conn, board = connect(board_file, kicad_cli_path=kicad_cli_path)
    try:
        fab_assets = export_kicad_fab_assets(board, fab_dir, api=kipy_api)
    finally:
        close = getattr(kicad_conn, "close", None)
        if callable(close):
            close()

    cfg = generate_gerber2ems_config(config)
    config_file = work_dir / "simulation.json"
    config_file.write_text(json.dumps(cfg, indent=2))

    simulator = KicadGerber2emsSimulator(executable=executable)
    result = simulator.run({"workdir": str(work_dir), "timeout_s": timeout_s})

    parsed = parse_gerber2ems_results(work_dir / "ems" / "results")

    warnings = list(fab_assets["warnings"])
    if drc["violation_count"] > 0:
        warnings.append(
            f"KiCad DRC found {drc['violation_count']} violation(s) on this board "
            "(shorts, clearance violations, or similar -- see result['drc']['violations'] "
            "for detail); the board still proceeded through export and simulation per "
            "CLAUDE.md's 'warn, never block' -- a human must review these before this "
            "board is sent to fab."
        )

    return {
        "provenance": result.provenance,
        "scope": (
            "PCB signal-integrity only (trace impedance, via/stackup "
            "S-parameters) -- NOT antenna far-field/gain; gerber2ems has "
            "no far-field capability at all (see module docstring)"
        ),
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "drc": drc,
        "fab_assets": fab_assets,
        "config_file": str(config_file),
        "computed": parsed["computed"],
        "ports": parsed["ports"],
        "note": parsed["note"],
        "warnings": warnings,
    }
