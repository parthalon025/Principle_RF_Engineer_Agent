import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .base import SimulationResult, Simulator, SimulatorError


class QucsSimulator(Simulator):
    name = "Qucs-S/qucsator"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("QUCSATOR_BIN", "qucsator_rf")

    def run(self, job: dict) -> SimulationResult:
        input_file = Path(job["input_file"]).resolve()
        workdir = Path(job.get("workdir", input_file.parent)).resolve()
        if not input_file.exists():
            raise SimulatorError(f"Input netlist not found: {input_file}")
        output_file = Path(job.get("output_file", input_file.with_suffix(".dat"))).resolve()

        # qucsator_rf's own CLI contract (see this module's header comment for
        # the full citation, ultimately src/ucs.cpp's argv-parsing loop):
        # "-i FILENAME" (input netlist, required for a non-interactive run)
        # and "-o FILENAME" (output dataset). UNLIKE NEC2++'s "-o -" stdout
        # convention (simulation/nec2pp.py), qucsator_rf's -o always fopen()s
        # the given name as a real file on disk (dataset::print(), src/
        # dataset.cpp) -- there is no special-cased "write dataset to stdout"
        # filename -- so this adapter always gives -o a real path and reads
        # that file back after the process exits, rather than trying to
        # capture the dataset from stdout. Progress/status text (not the
        # dataset itself) is redirected to stdout when -o is used
        # (redirect_status_to_stdout(), src/logging.c); real syntax/analysis
        # errors are always printed to stderr regardless -- both captured
        # below and stderr is what a nonzero exit's SimulatorError quotes.
        timeout_s = int(job.get("timeout_s", 600))
        try:
            completed = subprocess.run(
                [self.executable, "-i", str(input_file), "-o", str(output_file)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"Qucs-S/qucsator timed out after {timeout_s}s: {exc}") from exc
        if completed.returncode != 0:
            raise SimulatorError(
                f"Qucs-S/qucsator failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )
        if not output_file.exists():
            # Belt-and-braces: a 0 exit code should always mean the dataset
            # was written (ucs.cpp's out->print() runs unconditionally before
            # returning `ret`), but a fake/misbehaving executable in tests
            # (or an unexpected real-binary edge case) must not be silently
            # treated as a successful, empty run.
            raise SimulatorError(
                "Qucs-S/qucsator exited 0 but did not produce the expected "
                f"output dataset file: {output_file}"
            )

        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={
                "dataset": output_file.read_text(),
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )


# ---------------------------------------------------------------------------
# Qucs-S/qucsator netlist generation, execution, and S-parameter result
# parsing (issue #58) -- the free/GPL alternative to Keysight ADS's
# schematic-level circuit simulation (simulation/hfss.py already covers the
# licensed-EM-solver alternative to HFSS; ADS itself has no adapter here --
# see policies/tool_policy.yaml's "run_ads" approval_required entry).
#
# SOURCES CONSULTED (primary; all fetched directly from the upstream
# ra3xdh/qucsator_rf and ra3xdh/qucs_s GitHub repositories' default branches
# (develop / current respectively) during implementation, via GitHub's
# REST contents/git-trees API and the gh CLI -- see the per-fact citations
# below. Accessed 2026-09-02.):
#
#   - CLI invocation contract ("-i FILENAME" input netlist, "-o FILENAME"
#     output dataset, plain positional argv parsing with no config-file/GUI
#     dependency, nonzero return on netlist/analysis failure): src/ucs.cpp's
#     main() (the file `add_executable(qucsator_rf ucs.cpp ...)` in src/
#     CMakeLists.txt actually builds), ra3xdh/qucsator_rf. Corroborated by
#     doc/qucsator_rf.1 (the shipped man page) and by tests/runqucsator.sh
#     (the project's own test-suite CLI invocation: `"$qucsator" -i
#     "$simulfile"`), same repo.
#   - REAL DEFAULT EXECUTABLE NAME IS "qucsator_rf", NOT BARE "qucsator" --
#     this corrects the bare-"qucsator" name suggested in this ticket's own
#     text, verified two independent ways in ra3xdh/qucs_s (the GUI project
#     that drives this same engine): (1) qucs/main.cpp's own settings
#     resolution, `QucsSettings.Qucsator = QStandardPaths::findExecutable
#     ("qucsator_rf", {QucsSettings.BinDir})`, used whenever no explicit
#     "Qucsator" path is configured; (2) qucs/dialogs/simmessage.cpp
#     explicitly symlinks the real "qucsator_rf" binary to a temp file named
#     "qucsator" before invoking the third-party ASCO optimizer, with the
#     source comment "ASCO doesn't accept qucsator_rf name" -- i.e. the
#     *real* installed binary genuinely is named qucsator_rf; "qucsator" is
#     only ever a compatibility alias qucs_s itself constructs on the fly
#     for one specific external tool. This module therefore defaults to
#     "qucsator_rf" (overridable via the QUCSATOR_BIN env var or the
#     `executable=` constructor arg, matching simulation/nec2pp.py's
#     NEC2PP_BIN / simulation/openems.py's OPENEMS_BIN convention -- not to
#     be confused with qucs_s's own "QUCSATOR" env var, a different
#     application's full-path settings override with different semantics).
#   - NATIVE MULTI-PORT S-PARAMETER ANALYSIS, NOT A LEGACY-TOOL WORKAROUND:
#     the ".SP" netlist directive generated below maps directly onto
#     qucsator_rf's own `spsolver` class -- `struct define_t
#     spsolver::anadef = { "SP", 0, PROP_ACTION, ... }` in src/spsolver.cpp,
#     ra3xdh/qucsator_rf (the RF-focused, post-Qucs/Qucsator-fork simulation
#     kernel Qucs-S ships) -- which solves the FULL N-port S-matrix in one
#     run from however many Pac ports the netlist declares (spsolver::
#     saveResults(), same file, loops every circuit's every (i, j) S-matrix
#     entry once per swept frequency point). This is qucsator_rf's own
#     primary, intended analysis type, not a workaround through the
#     legacy pre-fork Qucs/Qucsator tool this project (github.com/
#     ra3xdh/qucsator_rf's own README: "Qucsator-RF is RF circuit
#     simulation kernel for Qucs-S") was forked from specifically to carry
#     forward.
#   - Netlist component-line syntax (`Type:InstanceName node1 node2
#     Key="Value" ...`, one component per line, quotes around values
#     optional per the grammar but always used here to match the verified
#     sample below; "#" starts a to-end-of-line comment; ground node is the
#     literal, hardcoded string "gnd" -- ucs.cpp's `gnd->setNode(0, "gnd")`
#     -- not configurable): a real fixture from qucsator_rf's own test
#     suite, tests/basic/u=ri/u=ri@sp.net (`Pac:P1 _net0 gnd Num="1"
#     Z="50 Ohm" P="0 dBm" f="1 GHz" Temp="26.85"` / `R:R1 _net0 gnd
#     R="50 Ohm" ...` / `.SP:SP1 Type="log" Start="1 Hz" Stop="10 GHz"
#     Points="101" Noise="no" ...`), cross-checked against the grammar
#     itself (src/scan_netlist.lpp, src/parse_netlist.ypp -- confirms
#     values may be bare or quoted, and that a bare number with no unit
#     suffix is always valid, which is what this module emits).
#   - Component property definitions (required vs. optional, per-property
#     defaults) for the four component types this module supports --
#     verified against each component's own PROP_REQ[]/PROP_OPT[] arrays
#     and its `struct define_t ...::cirdef`, ra3xdh/qucsator_rf:
#       * Pac (2-port AC power source used as an S-parameter port):
#         src/components/pac.cpp -- required f/Z/Num, optional P/Temp;
#         `calcSP()` in the same file confirms only "Z" (not "f"/"P")
#         actually feeds the S-parameter computation -- "f" is required by
#         the property schema but functionally inert for a `.SP` run
#         (it matters only for calcTR/calcHB, transient/harmonic-balance
#         analyses this module does not generate).
#       * R (resistor): src/components/resistor.cpp -- required R,
#         optional Temp/Tc1/Tc2/Tnom.
#       * L (inductor): src/components/inductor.cpp -- required L,
#         optional I.
#       * C (capacitor): src/components/capacitor.cpp -- required C,
#         optional V.
#       * TLIN (transmission line): src/components/tline.cpp -- required
#         Z/L, optional Alpha/Temp; `calcSP()` in the same file computes
#         the propagation phase as `2*pi*frequency/C0` (C0 = vacuum speed
#         of light, no separate effective-permittivity property exists on
#         this component) -- i.e. this is an IDEAL, non-dispersive
#         TEM line assuming free-space phase velocity; a caller modeling a
#         real microstrip/stripline trace must pre-compute an effective
#         electrical length itself (qucsator_rf's own MLIN microstrip
#         component would need its own separate substrate-property
#         verification pass, not done here -- an honestly scoped gap, not
#         a silent inaccuracy).
#   - ".SP" analysis directive's own property schema (Type/Start/Stop/
#     Points/Noise/NoiseIP/NoiseOP/saveCVs/saveAll, and Type's "lin"/"log"
#     values driving a Start/Stop/Points-based sweep): src/spsolver.cpp's
#     PROP_REQ[]/PROP_OPT[] + `struct define_t spsolver::anadef`, and
#     `analysis::createSweep()` in src/analysis.cpp ("Supported sweep
#     types are: linear, logarithmic, lists and constants" -- this module
#     only generates the linear/logarithmic Start/Stop/Points form, not
#     the list/constant forms spsolver also supports).
#   - S-parameter dataset variable naming -- "S[i,j]" with i/j the 1-based
#     port numbers taken directly from each Pac's own "Num" property (not
#     from netlist declaration order): `spsolver::saveResults()`/
#     `spsolver::createSP()` in src/spsolver.cpp (`res_i = ...
#     getPropertyInteger("Num")`, `n = createSP(res_i, res_j)`) and
#     `matvec::createMatrixString()` in src/matvec.cpp (`sprintf(str,
#     "%s[%d,%d]", n, r + 1, c + 1)`, called with 0-based r/c = Num-1 --
#     i.e. the printed indices ARE the 1-based Num values).
#   - Output "Qucs Dataset" text format -- `<indep NAME COUNT>...
#     </indep>` for the independent ("frequency") vector, `<dep NAME
#     dep-on...>...</dep>` per dependent vector, one number per line
#     inside each block: `dataset::print()`/`printDependency()`/
#     `printVariable()`/`printData()` in src/dataset.cpp. Numeric line
#     format verified from `printData()`'s own fprintf calls: a real value
#     prints as `  %+.20e` (sign-prefixed, 20-digit scientific); a complex
#     value with nonzero imaginary part prints as `  %+.20e%cj%.20e` where
#     %c is a literal '+' or '-' sign character immediately followed by a
#     literal 'j' and the (always non-negative) imaginary magnitude --
#     `parse_qucs_dataset()`'s numeric regex below is deliberately more
#     tolerant than this exact 20-digit form (matching this project's
#     existing openEMS-parser precedent of tolerant-not-byte-exact
#     regexes) since it has not been checked against a real binary's
#     actual output, only against this cited source.
#   - stdout/stderr split for error detection (status messages redirected
#     to stdout only when -o is given; real errors always on stderr):
#     src/logging.c (`file_error = file_status = stderr` at init;
#     `redirect_status_to_stdout()` only reassigns `file_status`).
#   - LICENSE: every source file cited above (src/ucs.cpp, src/pac.cpp,
#     src/spsolver.cpp, src/dataset.cpp, ...) carries the identical header
#     grant "it under the terms of the GNU General Public License as
#     published by the Free Software Foundation; either version 2, or (at
#     your option) any later version" -- the standard SPDX "GPL-2.0-or-
#     later" boilerplate -- confirmed identically in both ra3xdh/
#     qucsator_rf and ra3xdh/qucs_s. (GitHub's own repo-level license
#     badge for both repos reports the coarser "GPL-2.0", because that is
#     merely which license TEXT the plain COPYING file's contents match;
#     GitHub does not parse the "or (at your option) any later version"
#     grant out of individual source-file headers. The per-file header
#     text is the authoritative source for the actual license grant, per
#     standard GNU practice -- see docs/LICENSE_MATRIX.md's Qucs-S row.)
#
# SCOPE OF THIS IMPLEMENTATION:
#   - Components: R, L, C, TLIN (ideal line) only -- see the per-component
#     citations above. qucsator_rf ships dozens more (transistors,
#     microstrip MLIN/MCOUPLER/etc., transformers, ...); adding any of
#     those needs its own primary-source property verification pass, not
#     done here.
#   - Analysis: linear/logarithmic-swept `.SP` only (Start/Stop/Points);
#     the list/constant sweep forms and noise-parameter output (Noise is
#     always emitted as "no") are not generated or parsed by this pass --
#     an honestly scoped gap, not a silent inaccuracy.
#   - S-parameters ARE the full native N-port matrix in a SINGLE run (see
#     the "NATIVE MULTI-PORT" citation above) -- unlike simulation/
#     openems.py's FFT-based extraction (which only ever yields the
#     excited port's own column per run), every S[i,j] this module's
#     ports produce is populated from one qucsator_rf invocation, and (when
#     the ports are contiguously numbered 1..N) exported as a proper
#     Touchstone .sNp file via skrf for any N -- see
#     _try_write_touchstone() below.
#
# HONEST CAVEAT: the real `qucsator_rf` binary is NOT installed in this
# environment (confirmed via `which qucsator_rf` / `which qucsator`, both
# exit 1) and was not available to actually run against these generated
# netlists. Netlist generation and dataset parsing below are built to the
# letter of the documented/verified format above (real fixture files,
# grammar source, and result-writing source, all cited per-fact); they are
# exercised in tests only against a small fake "qucsator_rf" script (see
# tests/test_qucs.py) that mimics that documented CLI/dataset shape, NOT
# against a real qucsator_rf binary. Treat any result as unverified
# end-to-end until it has been run against the real tool at least once.
# ---------------------------------------------------------------------------


# Verified against each component's own PROP_REQ[] in qucsator_rf's
# src/components/*.cpp -- see this module's header comment citation.
_COMPONENT_REQUIRED_PROPS: dict[str, tuple[str, ...]] = {
    "R": ("R",),
    "L": ("L",),
    "C": ("C",),
    "TLIN": ("Z", "L"),
}


def _fmt_num(value: float) -> str:
    """Format a float as a compact, unit-suffix-free netlist value -- bare
    numbers (with or without an exponent) are always valid per the grammar
    cited in this module's header comment, so no "Ohm"/"Hz"/etc. suffix or
    SI-prefix letter is ever needed."""
    return f"{float(value):.10g}"


def _fmt_int(value: int) -> str:
    return str(int(value))


def generate_qucs_netlist(
    circuit: dict[str, Any],
    analysis: dict[str, Any],
    comment: str = "Generated by run_qucs_simulation",
) -> str:
    """Generate a qucsator_rf netlist from structured circuit/analysis input.

    `circuit` shape:
        {
          "ports": [                 # at least one required
              {
                "node": str,               # the non-ground node this port drives
                "num": int (optional, defaults to 1-based list position --
                    this is what indexes the returned S[num_i][num_j] matrix,
                    see this module's header comment's "S-parameter dataset
                    variable naming" citation),
                "name": str (optional, defaults to f"P{num}"),
                "z_ohms": float (default 50.0),          # Pac "Z"
                "power_dbm": float (default 0.0),        # Pac "P"
                "frequency_hz": float (optional, defaults to
                    analysis["start_hz"]) -- Pac's required "f" property;
                    functionally inert for a .SP run, see header comment.
              }, ...
          ],
          "components": [            # optional, e.g. a matching network
              {
                "type": "R" | "L" | "C" | "TLIN",
                "name": str (optional, defaults to f"{type}{index+1}"),
                "nodes": [node1, node2],
                "properties": {...},      # e.g. {"R": 50.0} for a resistor,
                    {"Z": 50.0, "L": 0.02} for a TLIN -- see
                    _COMPONENT_REQUIRED_PROPS and this module's header
                    comment's per-component citations for required keys;
                    any additional (optional) property from the cited
                    source is passed through verbatim.
              }, ...
          ],
        }

    `analysis` shape: {"sweep_type": "lin" (default) | "log", "start_hz":
    float (required), "stop_hz": float (required), "points": int (default
    201)} -- generates a single native multi-port `.SP` directive (see this
    module's header comment).

    The ground node is always the literal string "gnd" (hardcoded by
    qucsator_rf itself, not configurable -- see header comment); connect
    any node to ground by naming it "gnd" in a port's "node" or a
    component's "nodes".
    """
    ports = circuit.get("ports")
    if not ports:
        raise ValueError("circuit['ports'] must be a non-empty list")

    lines: list[str] = [f"# {comment}"]

    port_nums: list[int] = []
    for idx, port in enumerate(ports):
        if "node" not in port:
            raise ValueError(f"port {idx} missing required field 'node'")
        num = int(port.get("num", idx + 1))
        port_nums.append(num)
        name = port.get("name", f"P{num}")
        z_ohms = port.get("z_ohms", 50.0)
        power_dbm = port.get("power_dbm", 0.0)
        frequency_hz = port.get("frequency_hz", analysis.get("start_hz", 1e9))
        lines.append(
            f'Pac:{name} {port["node"]} gnd Num="{_fmt_int(num)}" '
            f'Z="{_fmt_num(z_ohms)}" P="{_fmt_num(power_dbm)}" '
            f'f="{_fmt_num(frequency_hz)}"'
        )
    if len(set(port_nums)) != len(port_nums):
        raise ValueError(f"circuit['ports'] 'num' values must be unique, got {port_nums}")

    for idx, comp in enumerate(circuit.get("components", [])):
        comp_type = comp.get("type")
        if comp_type not in _COMPONENT_REQUIRED_PROPS:
            raise ValueError(
                f"component {idx} 'type' must be one of "
                f"{sorted(_COMPONENT_REQUIRED_PROPS)}, got {comp_type!r}"
            )
        nodes = comp.get("nodes")
        if not nodes or len(nodes) != 2:
            raise ValueError(f"component {idx} ({comp_type}) requires exactly 2 'nodes'")
        name = comp.get("name", f"{comp_type}{idx + 1}")
        properties = dict(comp.get("properties", {}))
        missing = [p for p in _COMPONENT_REQUIRED_PROPS[comp_type] if p not in properties]
        if missing:
            raise ValueError(
                f"component {idx} ({comp_type}) missing required "
                f"propert{'y' if len(missing) == 1 else 'ies'}: {missing}"
            )
        prop_str = " ".join(f'{k}="{_fmt_num(v)}"' for k, v in properties.items())
        lines.append(f"{comp_type}:{name} {nodes[0]} {nodes[1]} {prop_str}")

    sweep_type = analysis.get("sweep_type", "lin")
    if sweep_type not in ("lin", "log"):
        raise ValueError(f"analysis['sweep_type'] must be 'lin' or 'log', got {sweep_type!r}")
    if "start_hz" not in analysis or "stop_hz" not in analysis:
        raise ValueError("analysis['start_hz'] and analysis['stop_hz'] are required")
    points = int(analysis.get("points", 201))
    lines.append(
        f'.SP:SP1 Type="{sweep_type}" Start="{_fmt_num(analysis["start_hz"])}" '
        f'Stop="{_fmt_num(analysis["stop_hz"])}" Points="{_fmt_int(points)}" Noise="no"'
    )

    return "\n".join(lines) + "\n"


# Matches one "<indep NAME COUNT>...</indep>" or "<dep NAME dep-on...>
# ...</dep>" block of a Qucs Dataset text file -- see this module's header
# comment's dataset.cpp citation. Vector names like "S[1,1]" contain no
# whitespace, so `\S+` captures the full bracketed name correctly.
_BLOCK_RE = re.compile(r"<(indep|dep)\s+(\S+)[^>]*>\r?\n(.*?)</\1>", re.DOTALL)

# Matches one printData() numeric line: a signed real (optionally
# scientific), optionally followed by a sign character, literal 'j', and a
# non-negative imaginary magnitude -- deliberately more tolerant than the
# exact "%+.20e" width printData() actually emits (see header comment).
_NUM_RE = re.compile(
    r"^\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)(?:([+-])j(\d*\.?\d+(?:[eE][+-]?\d+)?))?\s*$"
)

# Matches an S-parameter dependent-vector name, e.g. "S[1,1]", "S[2,1]" --
# the row/column are each a 1-based port "Num" value (see header comment).
_S_PARAM_RE = re.compile(r"^S\[(\d+),(\d+)\]$")


def parse_qucs_dataset(raw_text: str) -> dict[str, Any]:
    """Parse a qucsator_rf "Qucs Dataset" text file (as produced by
    `qucsator_rf -i ... -o <file>`) into a frequency list plus an
    S-parameter dict keyed "S<i><j>" (1-based port Num values), each value
    a list of [real, imag] pairs aligned with `frequency_hz`.

    See this module's header comment for the honest caveat: this has been
    verified against the *documented*/source-cited dataset format, not
    against real qucsator_rf output, since no real binary was available in
    this environment.
    """
    vectors: dict[str, list[complex]] = {}
    for _kind, name, body in _BLOCK_RE.findall(raw_text):
        values: list[complex] = []
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            m = _NUM_RE.match(line)
            if not m:
                continue
            real = float(m.group(1))
            imag = float(m.group(3)) if m.group(3) else 0.0
            if m.group(2) == "-":
                imag = -imag
            values.append(complex(real, imag))
        vectors[name] = values

    frequency_vec = vectors.get("frequency")
    frequency_hz = [c.real for c in frequency_vec] if frequency_vec else []

    values_out: dict[str, list[list[float]]] = {}
    for name, vec in vectors.items():
        m = _S_PARAM_RE.match(name)
        if not m:
            continue
        values_out[f"S{m.group(1)}{m.group(2)}"] = [[c.real, c.imag] for c in vec]

    if not frequency_hz or not values_out:
        return {
            "frequency_hz": frequency_hz,
            "s_parameters": {
                "computed": False,
                "note": (
                    "no 'frequency' independent vector and/or no 'S[i,j]' "
                    "dependent vectors were found in the qucsator_rf dataset "
                    "output -- the .SP analysis may not have run (check the "
                    "netlist/ports), or the output didn't match this "
                    "parser's expectations (see simulation/qucs.py's "
                    "module docstring)."
                ),
            },
        }

    return {
        "frequency_hz": frequency_hz,
        "s_parameters": {
            "computed": True,
            "values": values_out,
            "method": (
                "Native qucsator_rf spsolver .SP S-parameter analysis (a "
                "real circuit-theory computation from the netlist itself, "
                "not an FFT or other post-processing derivation) -- see "
                "simulation/qucs.py's module docstring citation."
            ),
            "note": "values[name] holds [real, imag] pairs per frequency_hz point.",
        },
    }


def _try_write_touchstone(
    workdir: Path,
    frequency_hz: list[float],
    values: dict[str, list[list[float]]],
    ports: list[dict[str, Any]],
) -> str | None:
    """Build an skrf.Network from the parsed S[i,j] values and write a
    Touchstone (.sNp) file, for any port count N, when every S_ij for a
    contiguous 1..N port numbering is present -- mirrors simulation/
    openems.py's own computed=True Touchstone convenience export (so
    rf_tools/correlation.py's touchstone_file/file lookup accepts this
    module's result directly). Returns None (never raises) when the ports
    aren't contiguously numbered 1..N, the S-matrix isn't fully populated,
    or skrf is unavailable/fails -- a missing convenience file must never
    hide the real S[i,j] values already returned in the caller's result."""
    if not frequency_hz or not values:
        return None
    n_ports = len(ports)
    try:
        z0_by_num = {
            int(p.get("num", idx + 1)): float(p.get("z_ohms", 50.0)) for idx, p in enumerate(ports)
        }
        if set(z0_by_num) != set(range(1, n_ports + 1)):
            return None
        z0 = [z0_by_num[i] for i in range(1, n_ports + 1)]

        n_freq = len(frequency_hz)
        s = np.zeros((n_freq, n_ports, n_ports), dtype=complex)
        for i in range(1, n_ports + 1):
            for j in range(1, n_ports + 1):
                key = f"S{i}{j}"
                if key not in values or len(values[key]) != n_freq:
                    return None
                s[:, i - 1, j - 1] = [complex(re, im) for re, im in values[key]]

        import skrf as rf

        network = rf.Network(
            frequency=rf.Frequency.from_f(np.array(frequency_hz) / 1e9, unit="ghz"),
            s=s,
            z0=z0,
        )
        touchstone_path = workdir / f"qucs_s_parameters.s{n_ports}p"
        network.write_touchstone(str(touchstone_path))
        return str(touchstone_path)
    except Exception:
        return None


def run_qucs_simulation(
    circuit: dict[str, Any],
    analysis: dict[str, Any],
    timeout_s: int = 600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate a qucsator_rf netlist from structured circuit/analysis
    input, run it via QucsSimulator, and parse the full native N-port
    S-parameter matrix out of the resulting dataset, tagged with SIMULATED
    provenance.

    See this module's header comment for the format-verification citations
    and the honest caveat: netlist generation and dataset parsing are built
    to the documented/verified qucsator_rf netlist and dataset formats, not
    to a real qucsator_rf binary run in this environment.
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="qucs_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    input_file = work_dir / "model.net"
    output_file = work_dir / "model.dat"
    input_file.write_text(generate_qucs_netlist(circuit, analysis))

    simulator = QucsSimulator(executable=executable)
    result = simulator.run(
        {
            "input_file": str(input_file),
            "output_file": str(output_file),
            "workdir": str(work_dir),
            "timeout_s": timeout_s,
        }
    )
    parsed = parse_qucs_dataset(result.outputs.get("dataset", ""))

    output: dict[str, Any] = {
        "provenance": "SIMULATED",
        "frequency_hz": parsed["frequency_hz"],
        "s_parameters": parsed["s_parameters"],
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "input_file": str(input_file),
        "output_file": str(output_file),
    }

    if parsed["s_parameters"].get("computed"):
        touchstone_file = _try_write_touchstone(
            work_dir, parsed["frequency_hz"], parsed["s_parameters"]["values"], circuit["ports"]
        )
        if touchstone_file:
            # Surfaced at top level (not just nested under s_parameters) so
            # it integrates with rf_tools.correlation.correlate_simulation_
            # measurement's own "touchstone_file"/"file" lookup, the same
            # way simulation/hfss.py's and simulation/openems.py's own
            # computed=True results already do.
            output["touchstone_file"] = touchstone_file

    return output
