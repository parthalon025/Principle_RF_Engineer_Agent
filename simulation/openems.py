import cmath
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .base import SimulationResult, Simulator, SimulatorError


class OpenemsSimulator(Simulator):
    name = "openEMS"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("OPENEMS_BIN") or "openEMS"

    def run(self, job: dict) -> SimulationResult:
        xml_file = Path(job["xml_file"]).resolve()
        workdir = Path(job.get("workdir", xml_file.parent)).resolve()
        if not xml_file.exists():
            raise SimulatorError(f"openEMS FDTD XML file not found: {xml_file}")

        # openEMS's own CLI contract (see module docstring citation): "Usage:
        # openEMS <FDTD_XML_FILE> [<options>...]" -- a single positional XML
        # file argument, then flags. --disable-dumps is passed by default
        # since this adapter does not read/parse the H5 field-dump files
        # openEMS would otherwise write (out of scope, see module docstring);
        # suppressing them keeps a run's on-disk footprint and runtime down.
        # An empty extra_args list restores the plain default invocation.
        extra_args = job.get("extra_args", ["--disable-dumps"])
        timeout_s = int(job.get("timeout_s", 3600))
        try:
            completed = subprocess.run(
                [self.executable, str(xml_file), *extra_args],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"openEMS timed out after {timeout_s}s: {exc}") from exc
        if completed.returncode != 0:
            raise SimulatorError(
                f"openEMS failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        # openEMS's per-timestep progress/energy log (parsed below for
        # convergence metadata) is printed throughout a run and can be long
        # for a real simulation, but the lines this module's parser actually
        # needs -- the final progress line, the "Time for N iterations..."
        # summary, and any max-timesteps warning -- are always at the *end*
        # of stdout, so (like the old pre-#38 stub) this tail-truncates
        # rather than keeping the full text; unlike NEC2++'s output (kept in
        # full in nec2pp.py, see that module for why), nothing this parser
        # reads lives earlier in the stream.
        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-8000:]},
        )


# ---------------------------------------------------------------------------
# openEMS FDTD-XML geometry/materials/ports/mesh generation, execution, and
# result parsing (issue #39).
#
# SOURCES CONSULTED (primary; all fetched directly from the upstream
# openEMS/CSXCAD GitHub repositories during implementation -- see the
# per-fact citations below):
#   - CLI invocation contract ("Usage: openEMS <FDTD_XML_FILE>
#     [<options>...]", and the --disable-dumps/--debug-material/
#     --debug-PEC/--debug-operator/--engine/--numThreads/--no-simulation/
#     --dump-statistics option set): openEMS's own showUsage()/
#     collectCommandLineArguments() in
#     github.com/thliebig/openEMS/blob/master/openems.cpp.
#   - End-criteria/timestep convergence semantics: the same openems.cpp --
#     RunFDTD()'s loop condition is
#     `(FDTD_Eng->GetNumberOfTimesteps()<NrTS) && (change>endCrit) &&
#     !CheckAbortCond()`, i.e. a run stops on *either* the max-timestep
#     count (NrTS, XML attribute "NumberOfTimesteps") or the energy decay
#     dropping below endCriteria (XML attribute "endCriteria" on the same
#     <FDTD> element, default 1e-5 per matlab/InitFDTD.m at the same repo,
#     1e-6 per the C++ Reset() default if the XML omits it).
#   - Console log formats used by parse_openems_output() below -- the
#     per-timestep progress line ("[@ TIME] Timestep: N || Speed: X MC/s
#     (Y s/TS) || Energy: ~Z (- WdB)"), the closing summary line ("Time for
#     N iterations with M.00 cells : S sec" / "Speed: R MCells/s"), and the
#     "Max. number of timesteps was reached before the end-criteria of
#     -NNdB was reached" warning: real sample output transcribed in
#     thliebig/openEMS-Project GitHub discussions/issues and a public
#     openEMS/pyEMS run-log gist (gist.github.com/biergaizi/
#     7f45c243f6e17b509bd1ea785a6af9e7), cross-referenced against the
#     endCriteria/NrTS semantics above from openems.cpp itself. NOT
#     re-verified against a real openEMS run in this environment (see the
#     HONEST CAVEAT below) -- unlike the NEC-2 guide's output, this text
#     was not read out of one single official reference document, so the
#     parser below matches these forms with tolerant regexes rather than
#     assuming byte-exact formatting.
#   - FDTD-XML file shape -- root element <openEMS> wrapping sibling <FDTD>
#     and <ContinuousStructure> elements: matlab/WriteOpenEMS.m in the
#     openEMS repo (`openEMS.FDTD = FDTD; openEMS.ContinuousStructure =
#     CSX; struct_2_xml(filename, openEMS, 'openEMS')`).
#   - <FDTD> attributes NumberOfTimesteps / endCriteria: matlab/InitFDTD.m
#     (`FDTD.ATTRIBUTE.NumberOfTimesteps=NrTS`, `FDTD.ATTRIBUTE.
#     endCriteria=endCrit`), confirming these are direct XML attributes of
#     the <FDTD> element (matching the QueryDoubleAttribute("endCriteria",
#     ...) read in openems.cpp).
#   - <ContinuousStructure CoordSystem="..."> and its <Properties>
#     container (children named after the property's own C++ class --
#     "Material", "Metal", "Excitation", "LumpedElement", "ProbeBox",
#     etc.) each holding a <Primitives> container (children "Box",
#     "Cylinder", etc.): ContinuousStructure::Write2XML/ReadFromXML in
#     github.com/thliebig/CSXCAD/blob/master/src/ContinuousStructure.cpp.
#   - <RectilinearGrid CoordSystem="..." DeltaUnit="..."> with child
#     <XLines Qty="N">v1,v2,...</XLines> (and Y/ZLines, comma-separated
#     text content): CSRectGrid::Write2XML in
#     github.com/thliebig/CSXCAD/blob/master/src/CSRectGrid.cpp.
#   - <Box>/<Cylinder> primitive geometry -- corner/axis points as child
#     elements <P1 .../><P2 .../> (not attributes of the primitive itself),
#     Cylinder additionally carrying a plain "Radius" attribute:
#     CSPrimBox.cpp and CSPrimCylinder.cpp Write2XML, same CSXCAD repo.
#     P1/P2's own X/Y/Z attribute form corroborated independently by a
#     third-party post-processing script description in
#     rdmontoya.wordpress.com/2020/06/17/ (decimal-locale fixups applied to
#     "P1/P2 coordinates (X, Y, Z)" and "Excitation Delay/Frequency"
#     attributes in real generated openEMS XML files).
#   - <Polygon Elevation="..." NormDir="..." QtyVertices="N"> primitive
#     geometry (issue #55) -- an "Elevation" plain attribute (position along
#     the out-of-plane axis) and an integer "NormDir" plain attribute (0/1/2
#     for the X/Y/Z axis the polygon's plane is perpendicular to), then one
#     child <Vertex X1="..." X2="..."/> element per in-plane vertex (X1/X2
#     being the two in-plane coordinates, not X/Y/Z -- CSXCAD picks which
#     physical axes those map to via NormDir): CSPrimPolygon::Write2XML in
#     github.com/thliebig/CSXCAD/blob/master/src/CSPrimPolygon.cpp, fetched
#     directly from that file during this pass (element tag name "Polygon"
#     confirmed via that same file's own PrimTypeName="Polygon" constructor
#     assignments, and via CSProperties::Write2XML's primitive-serialization
#     loop in CSProperties.cpp, which builds each primitive's XML tag from
#     its own GetTypeName()).
#   - <Material> Epsilon/Mue/Kappa/Sigma vector terms and <Excitation>
#     Type/Excite/Frequency/Delay terms: CSPropMaterial.cpp and
#     CSPropExcitation.cpp Write2XML, same CSXCAD repo -- WriteTerm(...)
#     (used for Radius, Frequency, Delay, R/C/L below) writes a plain
#     attribute on the element passed to it; WriteVectorTerm(...) (used for
#     Epsilon/Mue/Kappa/Sigma/Excite) writes a *child* element (named after
#     the term) carrying X/Y/Z attributes -- inferred from the P1/P2
#     child-element pattern above and the third-party script's own
#     independent read of real generated XML, not from reading
#     WriteVectorTerm's body directly (not fetched in this pass).
#   - <LumpedElement Direction="..." Caps="..." R="..." C="..." L="..."
#     LEtype="...">: CSPropLumpedElement.cpp Write2XML, same CSXCAD repo.
#   - AddLumpedPort(port_nr, R, start, stop, p_dir, excite) /
#     SetGaussExcite(f0, fc) call shapes (informing this module's job/
#     geometry dict shape, not its XML output): openEMS's own Python
#     interface docs and worked examples (docs.openems.de /
#     openems.readthedocs.io, "openEMS Python Interface"; thliebig/
#     openEMS-Project GitHub discussions #64 and #231).
#
# ADDITIONAL SOURCES CONSULTED FOR S-PARAMETER EXTRACTION (a code-review
# finding against issue #39's own acceptance criterion -- "S-parameters and
# far-field results are exported in the same structured, provenance-tagged
# form as other simulation results" -- fetched directly from
# github.com/thliebig/openEMS during this pass):
#   - <ProbeBox> element shape -- root attributes Number/Type/Weight/
#     NormDir/StartTime/StopTime/ModeFile, with the parent-class-inherited
#     tag name "ProbeBox" (per this module's own CSProperties-subclass
#     citation above): CSPropProbeBox.cpp's Write2XML,
#     github.com/thliebig/CSXCAD/blob/master/src/CSPropProbeBox.cpp.
#   - Per-port voltage/current ProbeBox construction -- a Type=0 (voltage)
#     probe with Weight=-1*V_Probe_Weight, and a Type=1 (current) probe
#     with a directional Weight and NormDir=<port axis>, both added via
#     AddProbe(CSX, name, type, ...) on the same port-gap primitive already
#     used for this module's Excitation/LumpedElement properties; each
#     probe's dump filename is its own property Name -- openEMS's own
#     high-level interface defaults these to "port_ut<N>"/"port_it<N>"
#     (N = 1-based port number): matlab/AddLumpedPort.m,
#     github.com/thliebig/openEMS/blob/master/matlab/AddLumpedPort.m. This
#     module uses its own descriptive probe names ("<port_name>_ut"/
#     "<port_name>_it", matching its existing "<port_name>_exc"/
#     "<port_name>_R" convention) rather than that numbered default -- any
#     name is valid as long as XML generation and result parsing agree on
#     it, which they do here.
#   - Port probe dump file format -- plain two-column ASCII (time, value),
#     read via MATLAB's plain `load(fullfile(path, filename))`, i.e. no
#     special binary/HDF5 encoding for these particular per-port U/I dumps:
#     matlab/ReadUI.m, github.com/thliebig/openEMS/blob/master/matlab/
#     ReadUI.m.
#   - Incident/reflected wave decomposition formula -- v_inc=(V+Z0*I)/2,
#     v_ref=(V-Z0*I)/2 (equivalently i_inc=(I+V/Z0)/2, i_ref=i_inc-I),
#     using each port's own reference impedance Z0: matlab/
#     calcLumpedPort.m, github.com/thliebig/openEMS/blob/master/matlab/
#     calcLumpedPort.m -- openEMS's own post-processing function for
#     exactly this module's lumped-port case. This module computes
#     S_ij(f)=v_ref_i(f)/v_inc_j(f) for the actually-excited port j, the
#     same ratio openEMS's own example scripts compute from calcPort's
#     output (e.g. "s11 = port{1}.uf.ref ./ port{1}.uf.inc"); only ports
#     sharing one common Z0 are supported (see SCOPE below) since a
#     rigorous mismatched-Z0 power-wave normalization
#     (sqrt(Z0_i/Z0_j) scaling) was not independently re-verified against
#     an openEMS worked example in this pass -- rather than guess that
#     factor, this module requires equal port impedances and says so.
#   - Time-to-frequency conversion -- matlab/DFT_time2freq.m,
#     github.com/thliebig/openEMS/blob/master/matlab/DFT_time2freq.m,
#     computes `sum(val .* exp(-1i*2*pi*f*t)) * dt` (pulse case, then
#     doubled for a single-sided spectrum). Since this module only ever
#     uses FFT output as a RATIO (v_ref/v_inc, both from the same kind of
#     transform applied consistently to every port's V(t)/I(t)), any
#     shared scale factor cancels -- so `numpy.fft.rfft`/`rfftfreq`
#     (unscaled) are used directly rather than reproducing that exact
#     dt/doubling normalization, which does not change the ratio.
#   - Confirmation that `--disable-dumps` (this module's own default extra
#     arg, unchanged by this pass) does NOT suppress ProbeBox voltage/
#     current output -- only field/nf2ff dump boxes check the
#     Enable_Dumps flag this option sets; ProbeBox-driven ProcessVoltage/
#     ProcessCurrent processors are constructed unconditionally in
#     SetupProcessing(): openems.cpp,
#     github.com/thliebig/openEMS/blob/master/openems.cpp.
#
# ADDITIONAL SOURCES CONSULTED FOR NF2FF FAR-FIELD/GAIN EXTRACTION (issue
# #269 -- fetched directly from github.com/thliebig/openEMS and
# github.com/thliebig/CSXCAD during this pass):
#   - <DumpBox> element shape -- root attributes DumpType/DumpMode/FileType/
#     MultiGridLevel (+ optional SubSampling/OptResolution), tag name
#     "DumpBox" (CSPropDumpBox::GetTypeXMLString(), CSPropDumpBox.h) reached
#     via the *parent* class's Write2XML first (CSPropDumpBox extends
#     CSPropProbeBox, so a DumpBox element also legally carries ProbeBox's
#     Number/Type/Weight/NormDir/StartTime/StopTime attributes -- this
#     module emits none of those since openEMS's own field-dump setup path,
#     openems.cpp's SetupProcessing() DUMPBOX loop, never reads them for a
#     field dump, only GetDumpType/GetMultiGridLevel/GetStartTime/
#     GetStopTime/GetFDSamples/GetDumpMode/GetFileType/GetSubSampling/
#     GetOptResolution -- so ReadFromXML's own documented defaults for the
#     unemitted ones are exactly what a real run would use anyway):
#     CSPropDumpBox.cpp/.h and CSPropProbeBox.cpp/.h,
#     github.com/thliebig/CSXCAD/blob/master/src/.
#   - DumpType numeric codes (0/1=E/H time-domain, 10/11=E/H frequency-
#     domain -- this module always uses 10/11, since a specific far-field
#     frequency list is exactly what an NF2FF box needs) and FileType (0=
#     VTK, 1=HDF5) / DumpMode (1=node-interpolation, CreateNF2FFBox.m's own
#     default) meanings, plus the 'Frequency' option's mapping onto a
#     literal FD_Samples child field: CSXCAD's matlab/AddDump.m,
#     github.com/thliebig/CSXCAD/blob/master/matlab/AddDump.m.
#   - The NF2FF recording box itself is NOT a single CSXCAD property type --
#     it is a *convention* of 12 separate DumpBox properties (one E + one H
#     dump per enclosing-box face: xn/xp/yn/yp/zn/zp), each a flat
#     (zero-thickness) Box primitive collapsed onto that face, named
#     "<name>_E_<face>"/"<name>_H_<face>": openEMS's own matlab/
#     CreateNF2FFBox.m, github.com/thliebig/openEMS/blob/master/matlab/
#     CreateNF2FFBox.m. This module follows that per-face-named-property
#     convention (not the alternative used by openEMS's own Python
#     interface, python/openEMS/nf2ff.py, which instead adds all 6 faces as
#     *primitives of a single* DumpBox property and disambiguates the
#     resulting per-primitive dump files by a positional index suffix, e.g.
#     "<name>_E_0.h5" -- chosen against here because that index is which
#     face gets written N-th, which SHIFTS whenever a 'directions' entry is
#     disabled, making the file name depend on which OTHER faces happen to
#     be enabled; CreateNF2FFBox.m's per-face stable names have no such
#     ambiguity).
#   - Confirmation that a DumpBox property's Name attribute becomes its
#     output filename verbatim (+ ".h5" for FileType=1, appended by the FD
#     dump writer) -- `ProcField->SetName(db->GetName()); ...
#     ProcField->SetFileName(ProcField->GetName());` in
#     openems.cpp::SetupProcessing()'s DUMPBOX loop, and
#     `m_HDF5_Dump_File = new HDF5_File_Writer(m_filename+".h5");` in
#     Common/processfields.cpp, both github.com/thliebig/openEMS/blob/
#     master/. The same SetupProcessing() loop is also this pass's source
#     for `ProcField->SetEnable(Enable_Dumps)` applying identically to
#     DumpBox-driven field dumps as it does to the ProbeBox case already
#     cited above -- confirming the acceptance criterion that a run
#     requesting an NF2FF box must not pass --disable-dumps.
#   - The standalone `nf2ff` command-line tool (a SEPARATE binary from
#     `openEMS` itself, built from the same source tree) -- CLI contract
#     "Usage: nf2ff <nf2ff-xml-file>": nf2ff/main.cpp,
#     github.com/thliebig/openEMS/blob/master/nf2ff/main.cpp.
#   - The nf2ff tool's own input-XML schema it parses in
#     nf2ff::AnalyseXMLNode() -- root element "nf2ff" with attributes
#     freq (comma-separated Hz list), Outfile (result HDF5 path), Radius
#     (meters, default 1), optional Center/Eps_r/Mue_r, LegacyHDF5 (an
#     Octave/MATLAB-only compatibility flag this module never sets, so the
#     tool's own default -- the modern, non-legacy layout below -- applies)
#     -- plus child elements <theta>/<phi> (comma-separated RADIANS, text
#     content) and one or more <Planes E_Field="..." H_Field="..."/>
#     (dump-file names, resolved relative to the tool's own working
#     directory, matching this module's own subprocess cwd=workdir
#     convention): nf2ff/nf2ff.cpp, github.com/thliebig/openEMS/blob/
#     master/nf2ff/nf2ff.cpp, cross-referenced against the MATLAB caller
#     that builds this same XML (openEMS/matlab/CalcNF2FF.m -- confirms the
#     'theta'/'phi' unit convention, "in radians", in its own docstring)
#     and the CLI's own `nf2ff <file>` invocation shape (CalcNF2FF.m's
#     `system([nf2ff_bin ' ' filename '.xml'])` on Windows).
#   - The nf2ff tool's own RESULT HDF5 schema, written by nf2ff::Write2HDF5
#     in the same nf2ff.cpp -- /Mesh/theta, /Mesh/phi, /Mesh/r (1-D
#     coordinate arrays); a /nf2ff group carrying attributes Frequency,
#     Prad (total radiated power per frequency, Watts), Dmax (peak
#     directivity per frequency, unitless linear); and per-frequency
#     datasets /nf2ff/E_theta/FD/f<n>, /nf2ff/E_phi/FD/f<n> (complex,
#     shape [n_theta, n_phi]) and /nf2ff/P_rad/FD/f<n> (real, W/m^2 at
#     the Radius above) -- independently corroborated by openEMS's own
#     Python result reader, python/openEMS/nf2ff.py's nf2ff_results class,
#     which reads this exact non-legacy layout.
#   - Confirmation that h5py reads/writes this complex HDF5 layout as an
#     ordinary numpy complex array with NO manual real/imag reassembly --
#     python/openEMS/nf2ff.py's own _ReadFD() docstring states outright:
#     "h5py maps the compound {r,i} type onto a native complex array" --
#     and the underlying C++ side confirms the field names are literally
#     "r"/"i" (HDF5_File_Reader::GetH5Type<complex<float>>() in
#     tools/hdf5_file_reader.cpp: `H5Tinsert(complex_id,"r",...);
#     H5Tinsert(complex_id,"i",...);` with the comment "create numpy
#     compatible complex128"). This is why this module's own test doubles
#     (tests/test_openems.py) can write synthetic NF2FF result files with
#     plain `h5py.File(...).create_dataset(name, data=<complex ndarray>)`
#     and this module can read them back with a plain `f[name][()]` -- no
#     legacy real/imag-split branch is implemented here (that branch exists
#     in openEMS's own MATLAB/Octave reader only, for tools that cannot
#     read HDF5 compound types at all).
#   - Directivity-from-(E_theta,E_phi,P_rad,Prad) formula --
#     D(theta,phi) = 4*pi*Radius^2*P_rad(theta,phi)/Prad_total, and
#     P_rad(theta,phi) = (|E_theta|^2+|E_phi|^2)/(2*Z0) -- read directly out
#     of the nf2ff tool's own far-field math, nf2ff/nf2ff_calc.cpp's
#     AddSinglePlane() (`P_rad(tn,pn) = abs(E_theta*conj(E_theta) +
#     E_phi*conj(E_phi))/(2*fZ0);`) and its `m_maxDir = P_max * (4*PI *
#     m_radius*m_radius / m_radPower);`, github.com/thliebig/openEMS/blob/
#     master/nf2ff/nf2ff_calc.cpp. This module recomputes directivity
#     per-angle from the raw E_theta/E_phi/P_rad/Prad arrays (rather than
#     trusting the tool's own separately-reported Dmax attribute) so that
#     the returned "pattern" table and "gain_dbi" (=max over that table,
#     mirroring simulation/nec2pp.py's own gain_dbi=max(pattern) approach)
#     are self-consistent from one source of truth.
#
# SCOPE OF THIS IMPLEMENTATION (explicitly narrower than a full openEMS
# feature set -- a scope decision made during this and the prior #39
# implementation pass, NOT quoted from GitHub issue #39 itself, which
# states plainly as an acceptance criterion that "S-parameters and
# far-field results are exported in the same structured, provenance-tagged
# form as other simulation results"; an earlier version of this comment
# incorrectly implied that text came from the ticket body):
#   - Geometry primitives: axis-aligned Box, Cylinder, and (added issue #55)
#     planar Polygon (no Sphere/Polyhedron/etc, though CSXCAD supports
#     more). Polygon covers arbitrary metamaterial/frequency-selective-
#     surface unit-cell outlines (split-ring resonators, Jerusalem crosses,
#     non-rectilinear elements) that Box/Cylinder alone can't express --
#     see geometry/unit_cell.py for a gdstk-based generator that builds
#     such outlines (via boolean composition of simpler box/polygon shapes)
#     and tiles them into a periodic planar array's worth of these Polygon
#     primitives, independent of this module.
#   - Materials: isotropic only (a single epsilon_r/mue_r/kappa applied
#     identically to X/Y/Z) -- CSXCAD's real per-axis anisotropic tensors
#     are not exposed here.
#   - Ports: modeled as one <Excitation> property (the drive signal), one
#     <LumpedElement> property (the R-ohm termination), and now (this pass)
#     a pair of <ProbeBox> voltage/current-recording properties, all
#     sharing the same port-gap box -- one Gaussian-pulse Frequency term
#     per port. openEMS's own AddLumpedPort() Python/MATLAB helper places
#     its U probe at the exact port midpoint and its I probe on a
#     perpendicular plane (see AddLumpedPort.m citation above); this module
#     places both probes on the same full port-gap box as a simplification,
#     since parse_openems_output() below reads the probes' *time-domain
#     dump files* (named after each probe's own Name attribute), not their
#     XML geometry, so this simplification does not affect what gets read.
#   - S-parameters: NOW COMPUTED (this pass) via FFT of the ProbeBox
#     voltage/current time-domain dumps -- see _compute_s_parameters_from_
#     probes() below and the "ADDITIONAL SOURCES" citations above for the
#     v_inc/v_ref decomposition and S_ij=v_ref_i/v_inc_j formula. Supported
#     for the port count(s) this module's XML generation already covers
#     (one or a few lumped ports, one active/excited at a time, matching
#     generate_openems_xml's own "excite" default), PROVIDED every port
#     shares one common resistance_ohms (Z0) -- mismatched port impedances
#     fall back to the honest computed=False path rather than guess at a
#     power-wave normalization factor not independently re-verified (see
#     citation above). A single excitation run only ever yields the
#     S-parameter *column* for the port actually excited (S_i,excited for
#     every port i) -- a full N-port matrix needs one run per excited port,
#     which this module does not orchestrate. For the single-port case
#     (this module's primary supported case, e.g. a patch antenna's S11)
#     that column IS the full 1x1 S-matrix, so a Touchstone (.s1p) file is
#     also written and surfaced as "touchstone_file", matching how
#     simulation/hfss.py's own computed=True S-parameters integrate with
#     rf_tools/correlation.py.
#   - Far-field/gain: NOW COMPUTED (issue #269) when `geometry['nf2ff']`
#     names a recording box (see generate_openems_xml's docstring for its
#     shape) -- via the real, separate `nf2ff` command-line tool (NOT part
#     of the `openEMS` binary itself; see the "ADDITIONAL SOURCES" above),
#     invoked as its own subprocess against the FD field dumps the FDTD run
#     wrote for that box. Returns computed=True with a real per-angle
#     "pattern" table and a real "gain_dbi" (structurally parallel to
#     NEC2++'s "impedance"/"pattern"/"gain_dbi" keys, so downstream code can
#     treat both simulators' results uniformly) whenever those dump files
#     exist and the nf2ff tool's result HDF5 parses as expected; falls back
#     to the honest computed=False path -- same as S-parameters -- when no
#     NF2FF box was requested at all, its dump files are missing from the
#     run's workdir (e.g. the geometry didn't actually request one, or a
#     real openEMS run named/laid out its dumps differently than this
#     module assumes), or the result HDF5 doesn't parse in the expected
#     shape. "s_parameters" keeps its own separate computed=False fallback
#     for its own separate reasons (missing port probe dumps, mismatched
#     port impedances) -- the two are independent code paths that can each
#     succeed or fail on their own.
#   - Convergence metadata (issue #39's other acceptance criterion) IS
#     real: it is parsed from openEMS's own progress/summary log text
#     (format cited above) to report whether a run's exit was end-criteria-
#     driven (energy decayed below endCriteria -- the mesh/excitation
#     converged) or hit max timesteps (NrTS reached first -- a signal the
#     mesh/excitation setup may need revision, per openEMS's own logged
#     warning), which is the signal actually available from a run's exit
#     condition.
#
# HONEST CAVEAT (issue #480: three distinct claims, not one). openEMS
# (v0.0.36 -- the Dockerfile's own comment explains it deliberately pins
# this over the newer v0.37.0-rc1/rc2, which are pre-release) is built from
# source and confirmed on PATH in this project's own Docker image
# (Dockerfile) -- it is NOT genuinely absent everywhere. It
# IS absent on a bare host outside that image (confirmed via `which openEMS`,
# exit 1, in this sandbox). And even inside the image, this code has never
# actually been DRIVEN against the real binary. XML generation follows the
# element/attribute names verified against CSXCAD/openEMS source as cited
# above; the console-log parser is exercised in tests only against a fake
# "openEMS" script (see tests/test_openems.py) whose sample log lines were
# transcribed from the third-party run logs cited above, not from output
# this implementation produced by actually running the real tool. Treat any
# result -- and in particular the exact wording match on the max-timesteps
# warning -- as unverified end-to-end until run against the real binary.
# The S-parameter FFT extraction added this pass is in the same position:
# the v_inc/v_ref/S_ij formulas and the ProbeBox/ReadUI file-format details
# are each cited to openEMS's own source above, but this module has never
# read an actual port_ut/port_it dump openEMS itself produced -- tests
# exercise it against a fake "openEMS" script extended to emit synthetic
# port time-domain data in the documented two-column ASCII shape (see
# tests/test_openems.py), with a closed-form known answer (a
# frequency-independent reflection/transmission coefficient) checked
# against this module's FFT output, not against real FDTD physics.
# The NF2FF far-field/gain extraction added in issue #269 is in the same
# position again, one level further removed: the real `nf2ff` binary lives
# in the same openEMS submodule source tree the Dockerfile's build targets
# (a separate executable from `openEMS` itself, cited above) -- expected on
# PATH there too, though (unlike `openEMS` itself, `nec2++`, `palace`,
# `qucsator_rf` and `ElmerSolver`/`ElmerGrid`) the Dockerfile has no
# explicit post-build `nf2ff --help`-style check confirming it specifically,
# so this is an inference from its build location, not an independently
# confirmed fact. Same absent-on-a-bare-host/never-driven-here shape either
# way, so neither has this module ever driven it against real FDTD near-field
# dumps. The DumpBox XML shape and the nf2ff tool's own
# input-XML/result-HDF5 schemas are each cited to openEMS/CSXCAD source
# above; tests exercise the XML generation directly and exercise the
# post-processing call chain (subprocess invocation, HDF5 result parsing,
# directivity/gain arithmetic) against a fake "nf2ff" script that writes a
# synthetic result HDF5 with a closed-form known answer (an isotropic
# radiator, and a single-direction-peaked pattern), not against real FDTD
# near-field data or a real nf2ff computation.
# ---------------------------------------------------------------------------


# x/y/z -> CSXCAD's own integer axis-index convention (0/1/2), shared by the
# port "direction" field (below, unchanged from before issue #55) and the
# new polygon primitive's "normal_axis" field (see _polygon_primitive_xml).
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def _fmt(value: float) -> str:
    return f"{float(value):.6g}"


def _p_element(tag: str, xyz: tuple[float, float, float]) -> str:
    x, y, z = xyz
    return f'<{tag} X="{_fmt(x)}" Y="{_fmt(y)}" Z="{_fmt(z)}"/>'


def _polygon_primitive_xml(prim: dict[str, Any]) -> str:
    """Render one Polygon primitive -- <Polygon Elevation="..." NormDir="..."
    QtyVertices="N"><Vertex X1="..." X2="..."/>...</Polygon> -- see module
    docstring citation for the CSPrimPolygon.cpp Write2XML source this was
    verified against (issue #55)."""
    if "points_m" not in prim:
        raise ValueError("polygon primitive requires 'points_m'")
    points = prim["points_m"]
    if len(points) < 3:
        raise ValueError(f"polygon primitive requires at least 3 points_m, got {len(points)}")
    normal_axis = prim.get("normal_axis", "z")
    if normal_axis not in _AXIS_INDEX:
        raise ValueError(
            f"polygon primitive 'normal_axis' must be 'x', 'y', or 'z', got {normal_axis!r}"
        )
    elevation = prim.get("elevation_m", 0.0)
    vertices = "".join(f'<Vertex X1="{_fmt(x)}" X2="{_fmt(y)}"/>' for x, y in points)
    return (
        f'<Polygon Elevation="{_fmt(elevation)}" NormDir="{_AXIS_INDEX[normal_axis]}" '
        f'QtyVertices="{len(points)}">' + vertices + "</Polygon>"
    )


def _primitive_xml(prim: dict[str, Any]) -> str:
    """Render one Box, Cylinder, or Polygon primitive (see module docstring
    citation for the P1/P2 child-element, Cylinder "Radius" attribute, and
    Polygon Vertex/NormDir/Elevation forms)."""
    shape = prim.get("shape", "box")
    if shape == "polygon":
        return _polygon_primitive_xml(prim)
    p1 = (prim["p1_m"][0], prim["p1_m"][1], prim["p1_m"][2])
    p2 = (prim["p2_m"][0], prim["p2_m"][1], prim["p2_m"][2])
    if shape == "box":
        return "<Box>" + _p_element("P1", p1) + _p_element("P2", p2) + "</Box>"
    if shape == "cylinder":
        if "radius_m" not in prim:
            raise ValueError("cylinder primitive requires 'radius_m'")
        return (
            f'<Cylinder Radius="{_fmt(prim["radius_m"])}">'
            + _p_element("P1", p1)
            + _p_element("P2", p2)
            + "</Cylinder>"
        )
    raise ValueError(f"shape must be 'box', 'cylinder', or 'polygon', got {shape!r}")


def _required_primitive_fields(prim: dict[str, Any]) -> tuple[str, ...]:
    """Which top-level fields a materials/conductors primitive dict must
    carry, before _primitive_xml is asked to render it -- shape-dependent
    since polygon's 'points_m' replaces box/cylinder's 'p1_m'/'p2_m'
    (issue #55)."""
    if prim.get("shape", "box") == "polygon":
        return ("points_m",)
    return ("p1_m", "p2_m")


# The six faces of an NF2FF recording box, in openEMS's own CreateNF2FFBox.m
# order (nd=1..3 for x/y/z, "n"=negative/start face then "p"=positive/stop
# face for each -- see module docstring citation). Index i's axis is i//2
# (0=x,1=y,2=z) and its sign is positive iff i is odd.
_NF2FF_DIRECTIONS = ("xn", "xp", "yn", "yp", "zn", "zp")
_NF2FF_DEFAULT_DIRECTIONS = (1, 1, 1, 1, 1, 1)


def _nf2ff_dump_names(name: str) -> dict[str, tuple[str, str]]:
    """The (E-dump-property-name, H-dump-property-name) pair for each NF2FF
    box face, given the box's own `name` -- "<name>_E_<face>"/
    "<name>_H_<face>", matching CreateNF2FFBox.m's own naming (see module
    docstring citation). A real openEMS run writes each as
    "<name>_E_<face>.h5"/"<name>_H_<face>.h5" in the run's workdir (Name
    attribute + ".h5", see citation)."""
    return {face: (f"{name}_E_{face}", f"{name}_H_{face}") for face in _NF2FF_DIRECTIONS}


def _nf2ff_face_primitive(
    p1_m: list[float], p2_m: list[float], axis: int, positive: bool
) -> dict[str, Any]:
    """A flat (zero-thickness) Box primitive dict covering one face of the
    NF2FF box spanned by p1_m (the 'start' corner) and p2_m (the 'stop'
    corner) -- the negative/start face collapses p2's `axis` coordinate onto
    p1's, the positive/stop face collapses p1's onto p2's, exactly mirroring
    CreateNF2FFBox.m's own "l_stop(nd) = start(nd)" / "l_start(nd) =
    stop(nd)" face construction (see module docstring citation)."""
    p1 = list(p1_m)
    p2 = list(p2_m)
    if positive:
        p1[axis] = p2[axis]
    else:
        p2[axis] = p1[axis]
    return {"shape": "box", "p1_m": p1, "p2_m": p2}


def _resolve_nf2ff_params(
    nf2ff_def: dict[str, Any], default_frequency_hz: float | None
) -> dict[str, Any]:
    """Validate and fill in defaults for a `geometry['nf2ff']` recording-box
    definition (see generate_openems_xml's docstring for the full field
    list) -- the single source of truth both generate_openems_xml (which
    only needs name/p1_m/p2_m/directions/frequencies_hz, for the FDTD-XML
    DumpBox emission) and the post-run NF2FF post-processing path (which
    additionally needs the angle grid/radius/center/eps_r/mue_r) resolve
    their defaults from, so the two can never silently drift apart."""
    missing = [f for f in ("p1_m", "p2_m") if f not in nf2ff_def]
    if missing:
        raise ValueError(f"geometry['nf2ff'] missing required field(s): {missing}")
    directions = list(nf2ff_def.get("directions", _NF2FF_DEFAULT_DIRECTIONS))
    if len(directions) != 6:
        raise ValueError(
            "geometry['nf2ff']['directions'] must have exactly 6 entries "
            f"(xn,xp,yn,yp,zn,zp), got {len(directions)}"
        )
    frequencies_hz = nf2ff_def.get("frequencies_hz")
    if not frequencies_hz:
        if default_frequency_hz is None:
            raise ValueError(
                "geometry['nf2ff'] needs 'frequencies_hz' (or a top-level "
                "geometry['frequency_hz']) -- the NF2FF FD_Samples dump "
                "needs at least one frequency to accumulate during the "
                "FDTD run"
            )
        frequencies_hz = [default_frequency_hz]
    center_m = nf2ff_def.get("center_m")
    return {
        "name": nf2ff_def.get("name", "nf2ff"),
        "p1_m": list(nf2ff_def["p1_m"]),
        "p2_m": list(nf2ff_def["p2_m"]),
        "directions": directions,
        "frequencies_hz": [float(f) for f in frequencies_hz],
        "radius_m": float(nf2ff_def.get("radius_m", 1.0)),
        "center_m": [float(v) for v in center_m] if center_m is not None else None,
        "eps_r": nf2ff_def.get("eps_r"),
        "mue_r": nf2ff_def.get("mue_r"),
        "theta_start_deg": float(nf2ff_def.get("theta_start_deg", 0.0)),
        "theta_step_deg": float(nf2ff_def.get("theta_step_deg", 10.0)),
        "theta_count": int(nf2ff_def.get("theta_count", 19)),
        "phi_start_deg": float(nf2ff_def.get("phi_start_deg", 0.0)),
        "phi_step_deg": float(nf2ff_def.get("phi_step_deg", 0.0)),
        "phi_count": int(nf2ff_def.get("phi_count", 1)),
    }


def generate_openems_xml(
    geometry: dict[str, Any],
    fdtd: dict[str, Any] | None = None,
    comment: str = "Generated by run_openems_simulation",
) -> str:
    """Generate an openEMS FDTD-XML simulation-description file from
    structured geometry/materials/ports/mesh input.

    `geometry` shape:
        {
          "materials": [                 # dielectric/lossy layers, optional
              {
                "name": str,
                "shape": "box" (default) | "cylinder" | "polygon",
                "p1_m", "p2_m": [x, y, z],   # corner/axis-endpoint points
                    # (box/cylinder only)
                "radius_m": float,           # cylinder only
                "points_m": [[x, y], ...],   # polygon only -- >=3 in-plane
                    # vertex coordinates, local to "normal_axis"'s plane
                "normal_axis": "x"|"y"|"z" (default "z"),   # polygon only --
                    # the axis the polygon's plane is perpendicular to
                "elevation_m": float (default 0.0),   # polygon only --
                    # position along normal_axis
                "epsilon_r": float (default 1.0),
                "mue_r": float (default 1.0),
                "kappa_s_m": float (default 0.0),   # electric conductivity
              }, ...
          ],
          "conductors": [                # PEC layers (patch, ground, etc.)
              {"name": str, "shape": "box"|"cylinder"|"polygon", "p1_m",
               "p2_m", "radius_m" (cylinder only), "points_m",
               "normal_axis", "elevation_m" (polygon only, see "materials"
               above -- e.g. a split-ring resonator or Jerusalem-cross
               frequency-selective-surface element, issue #55)}, ...
          ],
          "ports": [                     # at least one required
              {
                "name": str,
                "p1_m", "p2_m": [x, y, z],   # the port gap box
                "direction": "x" | "y" | "z",
                "resistance_ohms": float (default 50.0),
                "excite": bool (default True for the first port, else
                    False -- only one active/driven port is typical for a
                    single-port S11 sweep),
                "frequency_hz": float,   # Gaussian-pulse center frequency;
                    defaults to the top-level frequency_hz passed to
                    run_openems_simulation.
              }, ...
          ],
          "mesh": {                      # rectilinear mesh lines, meters
              "x_lines_m": [float, ...], "y_lines_m": [...], "z_lines_m": [...],
          },
          "nf2ff": {                      # optional (issue #269) -- a
              # near-field-to-far-field recording box; when present, a real
              # far_field/gain_dbi result is computed post-run (see
              # run_openems_simulation) instead of the permanent stub.
              "p1_m", "p2_m": [x, y, z],  # box start/stop corners -- must
                  # enclose every radiating structure (conductors/ports)
              "directions": [1, 1, 1, 1, 1, 1],  # optional, xn/xp/yn/yp/
                  # zn/zp enable flags (default: all 6 faces on)
              "name": str (default "nf2ff"),
              "frequencies_hz": [float, ...],  # optional, defaults to
                  # [geometry['frequency_hz']] -- far field is evaluated at
                  # exactly these frequencies (accumulated during the FDTD
                  # run itself, like a DFT, not resampled afterwards)
              "radius_m": float (default 1.0),   # far-field evaluation
                  # radius passed to the nf2ff tool
              "center_m": [x, y, z] (default [0, 0, 0]),  # nf2ff phase
                  # center -- must lie inside the box
              "eps_r", "mue_r": float (optional),  # background medium at
                  # the far-field radius, if not free space
              "theta_start_deg", "theta_step_deg": float, "theta_count": int,
              "phi_start_deg", "phi_step_deg": float, "phi_count": int,
                  # optional far-field angle grid (defaults mirror
                  # simulation/nec2pp.py's own RP-card pattern defaults: a
                  # single phi=0 deg cut, theta 0-180 deg in 10 deg steps)
          },
        }

    `fdtd` shape (all optional): {"max_timesteps": int (default 30000),
    "end_criteria": float (default 1e-5, the openEMS-documented default --
    see module docstring citation)}.

    Geometry is in meters; DeltaUnit is fixed at 1.0 (i.e. the mesh line
    values above are the actual meter coordinates, not scaled) since this
    module always emits already-metric mesh/primitive coordinates.
    """
    materials = geometry.get("materials", [])
    conductors = geometry.get("conductors", [])
    ports = geometry.get("ports")
    if not ports:
        raise ValueError("geometry['ports'] must be a non-empty list")
    mesh = geometry.get("mesh")
    if not mesh or not all(mesh.get(k) for k in ("x_lines_m", "y_lines_m", "z_lines_m")):
        raise ValueError(
            "geometry['mesh'] must supply non-empty 'x_lines_m'/'y_lines_m'/'z_lines_m'"
        )

    fdtd = fdtd or {}
    max_timesteps = int(fdtd.get("max_timesteps", 30000))
    end_criteria = float(fdtd.get("end_criteria", 1e-5))

    parts: list[str] = ["<openEMS>"]
    parts.append(
        f'<FDTD NumberOfTimesteps="{max_timesteps}" endCriteria="{_fmt(end_criteria)}">'
        f"<!-- {comment} --></FDTD>"
    )
    parts.append('<ContinuousStructure CoordSystem="0">')

    def _lines(values: list[float]) -> str:
        return ",".join(_fmt(v) for v in values)

    x_lines = mesh["x_lines_m"]
    y_lines = mesh["y_lines_m"]
    z_lines = mesh["z_lines_m"]
    parts.append(
        '<RectilinearGrid CoordSystem="0" DeltaUnit="1">'
        f'<XLines Qty="{len(x_lines)}">{_lines(x_lines)}</XLines>'
        f'<YLines Qty="{len(y_lines)}">{_lines(y_lines)}</YLines>'
        f'<ZLines Qty="{len(z_lines)}">{_lines(z_lines)}</ZLines>'
        "</RectilinearGrid>"
    )

    parts.append("<Properties>")

    for idx, mat in enumerate(materials):
        missing = [f for f in _required_primitive_fields(mat) if f not in mat]
        if missing:
            raise ValueError(f"material {idx} missing required field(s): {missing}")
        name = mat.get("name", f"material_{idx + 1}")
        eps = mat.get("epsilon_r", 1.0)
        mue = mat.get("mue_r", 1.0)
        kappa = mat.get("kappa_s_m", 0.0)
        parts.append(
            f'<Material Name="{name}">'
            + _p_element("Epsilon", (eps, eps, eps))
            + _p_element("Mue", (mue, mue, mue))
            + _p_element("Kappa", (kappa, kappa, kappa))
            + _p_element("Sigma", (0.0, 0.0, 0.0))
            + "<Primitives>"
            + _primitive_xml(mat)
            + "</Primitives>"
            + "</Material>"
        )

    for idx, cond in enumerate(conductors):
        missing = [f for f in _required_primitive_fields(cond) if f not in cond]
        if missing:
            raise ValueError(f"conductor {idx} missing required field(s): {missing}")
        name = cond.get("name", f"conductor_{idx + 1}")
        parts.append(
            f'<Metal Name="{name}"><Primitives>' + _primitive_xml(cond) + "</Primitives></Metal>"
        )

    default_frequency_hz = geometry.get("frequency_hz")
    for idx, port in enumerate(ports):
        required = ("p1_m", "p2_m", "direction")
        missing = [f for f in required if f not in port]
        if missing:
            raise ValueError(f"port {idx} missing required field(s): {missing}")
        direction = port["direction"]
        if direction not in _AXIS_INDEX:
            raise ValueError(f"port {idx} direction must be 'x', 'y', or 'z', got {direction!r}")
        ny = _AXIS_INDEX[direction]
        name = port.get("name", f"port_{idx + 1}")
        resistance = port.get("resistance_ohms", 50.0)
        excite = port.get("excite", idx == 0)
        frequency_hz = port.get("frequency_hz", default_frequency_hz)
        if excite and frequency_hz is None:
            raise ValueError(
                f"port {idx} is active (excite=True) but no frequency_hz was given "
                "(neither on the port nor as geometry['frequency_hz'])"
            )
        excite_vec = tuple(1.0 if a == ny else 0.0 for a in range(3))

        if excite:
            parts.append(
                f'<Excitation Name="{name}_exc" Type="0" '
                f'Frequency="{_fmt(frequency_hz)}" Delay="0">'
                + _p_element("Excite", excite_vec)
                + "<Primitives>"
                + _primitive_xml(port)
                + "</Primitives></Excitation>"
            )
        parts.append(
            f'<LumpedElement Name="{name}_R" Direction="{ny}" Caps="0" '
            f'R="{_fmt(resistance)}" C="0" L="0" LEtype="0">'
            + "<Primitives>"
            + _primitive_xml(port)
            + "</Primitives></LumpedElement>"
        )
        # Voltage (Type=0) and current (Type=1) ProbeBox properties, so a
        # real openEMS run writes the port_ut/port_it-style time-domain
        # dump files parse_openems_output()'s S-parameter extraction reads
        # (see this module's header comment citations for the ProbeBox
        # attribute shape, the Type=0/Weight=-1 + Type=1/Weight=1/NormDir
        # convention, and the placement simplification vs. AddLumpedPort.m).
        # Each probe's own Name is its dump filename.
        parts.append(
            f'<ProbeBox Name="{name}_ut" Type="0" Weight="-1">'
            + "<Primitives>"
            + _primitive_xml(port)
            + "</Primitives></ProbeBox>"
        )
        parts.append(
            f'<ProbeBox Name="{name}_it" Type="1" Weight="1" NormDir="{ny}">'
            + "<Primitives>"
            + _primitive_xml(port)
            + "</Primitives></ProbeBox>"
        )

    nf2ff_def = geometry.get("nf2ff")
    if nf2ff_def:
        nf2ff_params = _resolve_nf2ff_params(nf2ff_def, default_frequency_hz)
        freq_attr = ",".join(_fmt(f) for f in nf2ff_params["frequencies_hz"])
        dump_names = _nf2ff_dump_names(nf2ff_params["name"])
        for idx, face in enumerate(_NF2FF_DIRECTIONS):
            if not nf2ff_params["directions"][idx]:
                continue
            prim = _nf2ff_face_primitive(
                nf2ff_params["p1_m"], nf2ff_params["p2_m"], axis=idx // 2, positive=bool(idx % 2)
            )
            e_name, h_name = dump_names[face]
            # DumpType 10/11 = E/H frequency-domain dump, DumpMode=1 =
            # node-interpolation (CreateNF2FFBox.m's own default),
            # FileType=1 = HDF5 -- see module docstring citation. No
            # Number/Type/Weight/NormDir/StartTime/StopTime attributes
            # (ProbeBox's own, inherited by DumpBox) are emitted -- a real
            # openEMS run's field-dump setup never reads them, see
            # citation.
            for dump_type, dump_name in ((10, e_name), (11, h_name)):
                parts.append(
                    f'<DumpBox Name="{dump_name}" DumpType="{dump_type}" DumpMode="1" '
                    'FileType="1"><FD_Samples>'
                    + freq_attr
                    + "</FD_Samples><Primitives>"
                    + _primitive_xml(prim)
                    + "</Primitives></DumpBox>"
                )

    parts.append("</Properties>")
    parts.append("</ContinuousStructure>")
    parts.append("</openEMS>")
    return "\n".join(parts) + "\n"


# Matches openEMS's per-timestep progress line, e.g.
#   "[@ 4s] Timestep: 1326 || Speed: 88.8 MC/s (3.040e-03 s/TS) || Energy: ~7.06e-17 (- 0.00dB)"
# Tolerant of the exact whitespace/sign formatting since this was not
# verified byte-exact against a real binary (see module docstring caveat).
_PROGRESS_RE = re.compile(
    r"Timestep:\s*(\d+)\s*\|\|\s*Speed:\s*([\d.]+)\s*MC/s.*?\|\|\s*"
    r"Energy:\s*~?([\d.eE+-]+)\s*\(\s*-?\s*([\d.]+)\s*dB\)"
)

# Matches the closing summary line, e.g.
#   "Time for 14178 iterations with 269780.00 cells : 32.41 sec"
_SUMMARY_RE = re.compile(
    r"Time for\s*(\d+)\s*iterations with\s*([\d.]+)\s*cells\s*:\s*([\d.]+)\s*sec"
)

# Matches openEMS's speed report, e.g. "Speed: 118.02 MCells/s".
_SPEED_RE = re.compile(r"Speed:\s*([\d.]+)\s*MCells/s")

# Matches the warning openEMS logs when NrTS is hit before endCriteria is
# satisfied, e.g. "Max. number of timesteps was reached before the
# end-criteria of -50dB was reached". Matched loosely (not a fixed string)
# per the module docstring's caveat about this text's exact wording.
_MAX_TS_WARNING_RE = re.compile(
    r"max\.?\s*number of timesteps.*?(?:end.?criteria|end criteria)", re.IGNORECASE
)


# Minimum |v_inc(f)| at the excited port, as a fraction of that spectrum's
# own peak magnitude, for a frequency point to be reported. A Gaussian
# excitation pulse (this module's only excitation shape, see
# generate_openems_xml) carries negligible real energy far outside its
# designed bandwidth; S_ij(f)=v_ref_i(f)/v_inc_j(f) there divides by FFT
# noise, not signal, producing meaningless (not merely imprecise) values.
# This is a standard FDTD S-parameter post-processing practice (excluding
# the excitation's own low-energy tail), not a fabricated cutoff -- see
# this module's header comment for the DFT_time2freq.m citation this
# reasoning is paired with.
_S_PARAM_MIN_RELATIVE_MAGNITUDE = 1e-3


def _excited_port_index(ports: list[dict[str, Any]]) -> int:
    """Same default as generate_openems_xml's own per-port `excite` field:
    the first port with excite=True, else port 0."""
    for idx, port in enumerate(ports):
        if port.get("excite", idx == 0):
            return idx
    return 0


def _read_port_time_series(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read one openEMS port ProbeBox time-domain dump: plain two-column
    ASCII (time, value), '%'-prefixed comment lines ignored -- see this
    module's header comment's ReadUI.m citation. Returns (t, val)."""
    data = np.loadtxt(path, comments="%")
    data = np.atleast_2d(data)
    return data[:, 0].astype(float), data[:, 1].astype(float)


def _compute_s_parameters_from_probes(workdir: Path, ports: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute real S-parameters from openEMS's port_ut/port_it-style
    ProbeBox time-domain dumps in `workdir`, for the excited port actually
    driven (see _excited_port_index) -- see this module's header comment
    for the full v_inc/v_ref/S_ij formula citation. Returns a
    computed=False dict (with an explanatory note, never a guess) when the
    dump files aren't present or the ports don't share one common
    reference impedance -- both real, honestly-reported gaps, not silently
    worked around."""
    names = [port.get("name", f"port_{idx + 1}") for idx, port in enumerate(ports)]

    missing = [
        name
        for name in names
        if not (workdir / f"{name}_ut").exists() or not (workdir / f"{name}_it").exists()
    ]
    if missing:
        return {
            "computed": False,
            "note": (
                "S-parameter extraction needs each port's '<name>_ut'/"
                "'<name>_it' ProbeBox time-domain dump files in the run's "
                f"workdir; missing for port(s): {missing}. This can mean "
                "the run didn't actually execute (e.g. --no-simulation), "
                "the real openEMS binary doesn't dump these files under "
                "the name/format this module assumes (see module "
                "docstring's honest caveat), or (for a fake test "
                "executable) the fake script simply doesn't emit them."
            ),
        }

    z0_values = {float(port.get("resistance_ohms", 50.0)) for port in ports}
    if len(z0_values) != 1:
        return {
            "computed": False,
            "note": (
                f"ports have differing resistance_ohms {sorted(z0_values)} -- "
                "this module's S_ij=v_ref_i/v_inc_j formula (see module "
                "docstring citation) is only implemented for ports sharing "
                "one common reference impedance; a rigorous mismatched-Z0 "
                "power-wave normalization was not independently verified "
                "against an openEMS worked example in this pass, so this "
                "is an honest gap rather than a guessed formula."
            ),
        }
    z0 = next(iter(z0_values))

    excited_idx = _excited_port_index(ports)
    excited_name = names[excited_idx]

    t_ref: np.ndarray | None = None
    voltage_fd: dict[str, np.ndarray] = {}
    current_fd: dict[str, np.ndarray] = {}
    freqs: np.ndarray | None = None
    for name in names:
        t_v, v = _read_port_time_series(workdir / f"{name}_ut")
        t_i, i = _read_port_time_series(workdir / f"{name}_it")
        if len(t_v) != len(t_i) or not np.allclose(t_v, t_i):
            return {
                "computed": False,
                "note": (
                    f"port {name!r}'s voltage and current probe dumps don't "
                    "share the same time samples -- can't decompose "
                    "incident/reflected waves without a common time base."
                ),
            }
        if t_ref is None:
            t_ref = t_v
            dt = float(np.mean(np.diff(t_ref))) if len(t_ref) > 1 else 1.0
            freqs = np.fft.rfftfreq(len(t_ref), d=dt)
        elif len(t_v) != len(t_ref) or not np.allclose(t_v, t_ref):
            return {
                "computed": False,
                "note": (
                    f"port {name!r}'s probe dump time samples don't match "
                    f"port {excited_name!r}'s -- can't FFT ports against a "
                    "common frequency grid."
                ),
            }
        voltage_fd[name] = np.fft.rfft(v)
        current_fd[name] = np.fft.rfft(i)

    v_inc = {name: 0.5 * (voltage_fd[name] + z0 * current_fd[name]) for name in names}
    v_ref = {name: 0.5 * (voltage_fd[name] - z0 * current_fd[name]) for name in names}

    denom = v_inc[excited_name]
    peak = float(np.max(np.abs(denom))) if len(denom) else 0.0
    if peak <= 0.0:
        return {
            "computed": False,
            "note": (
                f"excited port {excited_name!r}'s incident-wave spectrum "
                "is identically zero -- nothing to normalize S-parameters "
                "against (check the excitation actually ran)."
            ),
        }
    mask = np.abs(denom) >= _S_PARAM_MIN_RELATIVE_MAGNITUDE * peak
    if not np.any(mask):
        return {
            "computed": False,
            "note": (
                "no frequency point met the "
                f"{_S_PARAM_MIN_RELATIVE_MAGNITUDE:g}x-of-peak incident-wave "
                "magnitude threshold used to exclude FFT noise outside the "
                "excitation pulse's bandwidth -- nothing usable to report."
            ),
        }

    frequency_hz = freqs[mask]
    values: dict[str, list[list[float]]] = {}
    for i_idx, name in enumerate(names):
        s_name = f"S{i_idx + 1}{excited_idx + 1}"
        s_vals = v_ref[name][mask] / denom[mask]
        values[s_name] = [[complex(v).real, complex(v).imag] for v in s_vals]

    result: dict[str, Any] = {
        "computed": True,
        "method": (
            "FFT (numpy.fft.rfft) of ProbeBox port voltage/current "
            "time-domain dumps; v_inc=(V+Z0*I)/2, v_ref=(V-Z0*I)/2 per "
            "openEMS's own calcLumpedPort.m, S_ij(f)=v_ref_i(f)/v_inc_j(f) "
            "for the excited port j -- see simulation/openems.py's module "
            "docstring for the full citation."
        ),
        "excited_port": excited_name,
        "z0_ohms": z0,
        "frequency_hz": frequency_hz.tolist(),
        "values": values,
        "note": (
            "values[name] holds [real, imag] pairs per frequency_hz point. "
            f"Only the excited port's own column was computed (port "
            f"{excited_name!r} was the only one driven this run) -- a full "
            "N-port S-matrix would need one run per excited port, not "
            "orchestrated here."
            if len(names) > 1
            else "values[name] holds [real, imag] pairs per frequency_hz point."
        ),
    }

    if len(names) == 1:
        try:
            import skrf as rf

            s = np.array([complex(re, im) for re, im in values["S11"]], dtype=complex).reshape(
                -1, 1, 1
            )
            network = rf.Network(
                frequency=rf.Frequency.from_f(frequency_hz / 1e9, unit="ghz"),
                s=s,
                z0=z0,
            )
            touchstone_path = workdir / "openems_s_parameters.s1p"
            network.write_touchstone(str(touchstone_path))
            result["touchstone_file"] = str(touchstone_path)
        except Exception:
            # Touchstone export is a convenience for rf_tools/correlation.py
            # integration (matching simulation/hfss.py's own computed=True
            # pattern), not the acceptance criterion itself -- a failure
            # here (e.g. skrf unavailable) must not hide the real, already-
            # computed S-parameter values above.
            pass

    return result


# ---------------------------------------------------------------------------
# NF2FF far-field/gain post-processing (issue #269) -- invokes the real,
# separate `nf2ff` command-line tool against the FD field dumps the FDTD run
# wrote for a geometry['nf2ff'] recording box, then parses its result HDF5
# into a per-angle "pattern" table plus a "gain_dbi" number, structurally
# parallel to simulation/nec2pp.py's own pattern/gain_dbi (see this module's
# header comment for the full citation list).
# ---------------------------------------------------------------------------


def _locate_nf2ff_plane_files(
    workdir: Path, name: str, directions: list[int]
) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Which of the up-to-6 NF2FF E/H dump-file pairs (see
    _nf2ff_dump_names) actually exist in `workdir`, for the enabled faces in
    `directions`. Returns (found, missing) -- found is a list of (face,
    e_filename, h_filename) with BARE filenames (the nf2ff tool resolves
    Plane filenames relative to its own working directory, matching this
    module's subprocess cwd=workdir convention -- see module docstring
    citation), missing lists the enabled face(s) whose dump pair wasn't
    found (never a partial/guessed reading of an incomplete pair)."""
    dump_names = _nf2ff_dump_names(name)
    found: list[tuple[str, str, str]] = []
    missing: list[str] = []
    for idx, face in enumerate(_NF2FF_DIRECTIONS):
        if not directions[idx]:
            continue
        e_name, h_name = dump_names[face]
        e_file, h_file = f"{e_name}.h5", f"{h_name}.h5"
        if (workdir / e_file).exists() and (workdir / h_file).exists():
            found.append((face, e_file, h_file))
        else:
            missing.append(face)
    return found, missing


def _generate_nf2ff_config_xml(
    outfile: str,
    frequencies_hz: list[float],
    theta_rad: np.ndarray,
    phi_rad: np.ndarray,
    planes: list[tuple[str, str, str]],
    radius_m: float,
    center_m: list[float] | None,
    eps_r: float | None,
    mue_r: float | None,
) -> str:
    """Build the nf2ff tool's own input-XML control file -- root element
    "nf2ff" with freq/Outfile/Radius(+optional Center/Eps_r/Mue_r)
    attributes, <theta>/<phi> child elements (radians, comma-separated), and
    one <Planes E_Field=".../ H_Field="..."/> per recorded box face -- see
    this module's header comment for the full nf2ff::AnalyseXMLNode()
    citation. Pure string-building, no I/O."""
    attrs = [
        f'freq="{",".join(_fmt(f) for f in frequencies_hz)}"',
        f'Outfile="{outfile}"',
        f'Radius="{_fmt(radius_m)}"',
    ]
    if center_m is not None:
        attrs.append(f'Center="{",".join(_fmt(v) for v in center_m)}"')
    if eps_r is not None:
        attrs.append(f'Eps_r="{_fmt(eps_r)}"')
    if mue_r is not None:
        attrs.append(f'Mue_r="{_fmt(mue_r)}"')
    planes_xml = "".join(f'<Planes E_Field="{e}" H_Field="{h}"/>' for _, e, h in planes)
    theta_text = ",".join(_fmt(v) for v in theta_rad)
    phi_text = ",".join(_fmt(v) for v in phi_rad)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<nf2ff {' '.join(attrs)}>"
        f"<theta>{theta_text}</theta><phi>{phi_text}</phi>" + planes_xml + "</nf2ff>\n"
    )


def _build_far_field_result(
    frequencies_hz: list[float],
    theta_rad: np.ndarray,
    phi_rad: np.ndarray,
    e_theta_by_freq: list[np.ndarray],
    e_phi_by_freq: list[np.ndarray],
    p_rad_by_freq: list[np.ndarray],
    prad_total_by_freq: list[float],
    radius_m: float,
) -> dict[str, Any]:
    """Turn the nf2ff tool's raw per-frequency (E_theta, E_phi, P_rad,
    Prad_total) arrays into a per-angle "pattern" table plus a "gain_dbi"
    number -- pure arithmetic, no I/O, directly unit-testable against
    hand-picked arrays with a known closed-form answer.

    Directivity(theta,phi) = 4*pi*radius_m^2*P_rad(theta,phi)/Prad_total,
    per nf2ff/nf2ff_calc.cpp's own m_maxDir formula (see module docstring
    citation) -- computed here per-angle (not read from the tool's own
    separately-reported Dmax attribute) so "pattern" and "gain_dbi" share
    one source of truth, mirroring simulation/nec2pp.py's own
    gain_dbi=max(pattern) approach. A directivity of exactly 0 (no power
    radiated in that direction) is reported as -999.0 dBi, matching
    nec2pp's own sentinel for a "not a real number" pattern entry -- such
    points are excluded from the gain_dbi max, same as nec2pp's own
    valid_totals filter.
    """
    pattern: list[dict[str, Any]] = []
    for f_idx, freq_hz in enumerate(frequencies_hz):
        e_theta = e_theta_by_freq[f_idx]
        e_phi = e_phi_by_freq[f_idx]
        p_rad = p_rad_by_freq[f_idx]
        prad_total = prad_total_by_freq[f_idx]
        for t_idx, theta in enumerate(theta_rad):
            for p_idx, phi in enumerate(phi_rad):
                if prad_total > 0.0:
                    directivity_linear = (
                        4.0 * math.pi * radius_m**2 * p_rad[t_idx, p_idx] / prad_total
                    )
                else:
                    directivity_linear = 0.0
                directivity_dbi = (
                    10.0 * math.log10(directivity_linear) if directivity_linear > 0.0 else -999.0
                )
                et = complex(e_theta[t_idx, p_idx])
                ep = complex(e_phi[t_idx, p_idx])
                pattern.append(
                    {
                        "frequency_hz": freq_hz,
                        "theta_deg": math.degrees(theta),
                        "phi_deg": math.degrees(phi),
                        "directivity_dbi": directivity_dbi,
                        "e_theta_v_per_m": abs(et),
                        "e_theta_phase_deg": math.degrees(cmath.phase(et)),
                        "e_phi_v_per_m": abs(ep),
                        "e_phi_phase_deg": math.degrees(cmath.phase(ep)),
                    }
                )

    valid = [row["directivity_dbi"] for row in pattern if row["directivity_dbi"] > -999.0]
    gain_dbi = max(valid) if valid else None

    return {
        "computed": True,
        "method": (
            "nf2ff (openEMS's separate near-field-to-far-field "
            "post-processing tool): Directivity(theta,phi) = "
            "4*pi*radius_m^2*P_rad(theta,phi)/Prad_total, gain_dbi = "
            "max(10*log10(Directivity)) over the sampled (frequency, theta, "
            "phi) grid below -- see simulation/openems.py's module "
            "docstring for the full citation."
        ),
        "radius_m": radius_m,
        "frequency_hz": list(frequencies_hz),
        "prad_w": list(prad_total_by_freq),
        "pattern": pattern,
        "gain_dbi": gain_dbi,
        "note": (
            "gain_dbi is peak DIRECTIVITY across the sampled grid in "
            "'pattern' (no port-mismatch or extra loss beyond what the FDTD "
            "materials already modeled is subtracted) -- narrower/coarser "
            "than the antenna's true 3-D peak if the swept theta/phi grid "
            "doesn't include its actual maximum-radiation direction."
        ),
    }


def _compute_far_field_from_nf2ff(
    workdir: Path,
    nf2ff_def: dict[str, Any],
    default_frequency_hz: float | None,
    executable: str | None = None,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Orchestrate the real NF2FF far-field/gain computation: locate the FD
    field dump files the FDTD run wrote for `nf2ff_def`'s recording box,
    build and run the nf2ff tool's own input-XML config against them, then
    parse its result HDF5 into far_field/gain_dbi. Returns
    {"far_field": {...}, "gain_dbi": ...} -- computed=False (with a
    specific, distinguishing note, never a guess) when the dump files are
    missing or the result HDF5 doesn't parse as expected; raises
    SimulatorError (matching OpenemsSimulator.run()'s own style) only for a
    genuine tool failure (nonzero exit, timeout) -- see module docstring's
    "warn, never block" convention."""
    resolved = _resolve_nf2ff_params(nf2ff_def, default_frequency_hz)
    found, missing = _locate_nf2ff_plane_files(workdir, resolved["name"], resolved["directions"])
    if not found:
        return {
            "far_field": {
                "computed": False,
                "note": (
                    "no NF2FF E/H field dump files found in the run's "
                    f"workdir for box {resolved['name']!r} (looked for "
                    f"face(s) {missing}) -- this can mean the run didn't "
                    "actually write dumps (was --disable-dumps still "
                    "passed?), the real openEMS binary names/lays out its "
                    "dump files differently than this module assumes (see "
                    "module docstring's honest caveat), or (for a fake "
                    "test executable) the fake script simply doesn't emit "
                    "them."
                ),
            },
            "gain_dbi": None,
        }

    theta_rad = np.deg2rad(
        resolved["theta_start_deg"]
        + resolved["theta_step_deg"] * np.arange(resolved["theta_count"])
    )
    phi_rad = np.deg2rad(
        resolved["phi_start_deg"] + resolved["phi_step_deg"] * np.arange(resolved["phi_count"])
    )

    xml_text = _generate_nf2ff_config_xml(
        outfile=f"{resolved['name']}.h5",
        frequencies_hz=resolved["frequencies_hz"],
        theta_rad=theta_rad,
        phi_rad=phi_rad,
        planes=found,
        radius_m=resolved["radius_m"],
        center_m=resolved["center_m"],
        eps_r=resolved["eps_r"],
        mue_r=resolved["mue_r"],
    )
    xml_path = workdir / f"{resolved['name']}_nf2ff.xml"
    xml_path.write_text(xml_text)

    nf2ff_bin = executable or os.getenv("NF2FF_BIN") or "nf2ff"
    try:
        completed = subprocess.run(
            [nf2ff_bin, str(xml_path)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulatorError(f"nf2ff timed out after {timeout_s}s: {exc}") from exc
    if completed.returncode != 0:
        raise SimulatorError(f"nf2ff failed ({completed.returncode}): {completed.stderr[-4000:]}")

    result_path = workdir / f"{resolved['name']}.h5"
    if not result_path.exists():
        return {
            "far_field": {
                "computed": False,
                "note": (
                    f"nf2ff exited successfully but did not write the "
                    f"expected result file {result_path.name!r} -- nothing "
                    "to read."
                ),
            },
            "gain_dbi": None,
        }

    import h5py

    n_freq = len(resolved["frequencies_hz"])
    try:
        with h5py.File(result_path, "r") as f:
            prad_total_by_freq = [float(v) for v in np.asarray(f["/nf2ff"].attrs["Prad"])]
            e_theta_by_freq = [np.asarray(f[f"/nf2ff/E_theta/FD/f{n}"][()]) for n in range(n_freq)]
            e_phi_by_freq = [np.asarray(f[f"/nf2ff/E_phi/FD/f{n}"][()]) for n in range(n_freq)]
            p_rad_by_freq = [
                np.asarray(f[f"/nf2ff/P_rad/FD/f{n}"][()], dtype=float) for n in range(n_freq)
            ]
    except (OSError, KeyError) as exc:
        return {
            "far_field": {
                "computed": False,
                "note": (
                    f"nf2ff wrote {result_path.name!r} but this module "
                    "could not read the expected /nf2ff/.../FD/f<N> "
                    f"datasets or the /nf2ff 'Prad' attribute from it "
                    f"({exc!r}) -- either the real nf2ff binary's result "
                    "HDF5 schema differs from what this module assumes "
                    "(see module docstring's honest caveat), or the number "
                    f"of frequencies it computed doesn't match the "
                    f"{n_freq} requested."
                ),
            },
            "gain_dbi": None,
        }

    far_field = _build_far_field_result(
        frequencies_hz=resolved["frequencies_hz"],
        theta_rad=theta_rad,
        phi_rad=phi_rad,
        e_theta_by_freq=e_theta_by_freq,
        e_phi_by_freq=e_phi_by_freq,
        p_rad_by_freq=p_rad_by_freq,
        prad_total_by_freq=prad_total_by_freq,
        radius_m=resolved["radius_m"],
    )
    far_field["hdf5_file"] = str(result_path)
    gain_dbi = far_field.pop("gain_dbi")
    return {"far_field": far_field, "gain_dbi": gain_dbi}


def parse_openems_output(
    raw_output: str,
    end_criteria: float = 1e-5,
    max_timesteps: int | None = None,
    workdir: str | Path | None = None,
    ports: list[dict[str, Any]] | None = None,
    nf2ff: dict[str, Any] | None = None,
    default_frequency_hz: float | None = None,
    nf2ff_executable: str | None = None,
    nf2ff_timeout_s: int = 600,
) -> dict[str, Any]:
    """Parse openEMS console/log text into convergence metadata plus real
    (when `workdir`+`ports` are given and the port probe dump files are
    present -- see _compute_s_parameters_from_probes) or honestly-stubbed
    S-parameter and far-field keys.

    Convergence metadata is real, parsed from the progress/summary log
    lines and max-timesteps warning cited in this module's header comment.
    `terminated_reason` is:
      - "max_timesteps" if the logged max-timesteps warning is present, or
        (as a fallback signal) the final logged timestep is at/above
        max_timesteps;
      - "end_criteria" if a final progress line was found and the run
        stopped short of max_timesteps (the ordinary, converged case);
      - "unknown" if no progress line could be parsed at all (e.g. an
        empty or unrecognized log -- this is the honest fallback, not a
        guess dressed up as a signal).
    """
    progress_matches = list(_PROGRESS_RE.finditer(raw_output))
    final_timestep: int | None = None
    final_energy_linear: float | None = None
    final_energy_db: float | None = None
    if progress_matches:
        last = progress_matches[-1]
        final_timestep = int(last.group(1))
        final_energy_linear = float(last.group(3))
        final_energy_db = -float(last.group(4))

    summary_match = _SUMMARY_RE.search(raw_output)
    total_timesteps = int(summary_match.group(1)) if summary_match else final_timestep
    total_cells = float(summary_match.group(2)) if summary_match else None
    elapsed_s = float(summary_match.group(3)) if summary_match else None

    speed_match = _SPEED_RE.search(raw_output)
    speed_mcells_per_s = float(speed_match.group(1)) if speed_match else None

    hit_max_warning = bool(_MAX_TS_WARNING_RE.search(raw_output))
    if hit_max_warning or (
        max_timesteps is not None
        and total_timesteps is not None
        and total_timesteps >= max_timesteps
    ):
        terminated_reason = "max_timesteps"
    elif total_timesteps is not None:
        terminated_reason = "end_criteria"
    else:
        terminated_reason = "unknown"

    convergence = {
        "terminated_reason": terminated_reason,
        "final_timestep": total_timesteps,
        "max_timesteps": max_timesteps,
        "end_criteria": end_criteria,
        "final_energy_linear": final_energy_linear,
        "final_energy_db": final_energy_db,
        "total_cells": total_cells,
        "elapsed_s": elapsed_s,
        "speed_mcells_per_s": speed_mcells_per_s,
    }

    if workdir is not None and ports:
        s_parameters = _compute_s_parameters_from_probes(Path(workdir), ports)
    else:
        s_parameters = {
            "computed": False,
            "note": (
                "S-parameter extraction needs the run's workdir and port "
                "list (to locate each port's ProbeBox time-domain dump "
                "files) -- neither was given to parse_openems_output(), so "
                "nothing was read. See simulation/openems.py's module "
                "docstring 'SCOPE OF THIS IMPLEMENTATION' for what's "
                "computed when they are."
            ),
        }
    if workdir is not None and nf2ff:
        nf2ff_result = _compute_far_field_from_nf2ff(
            Path(workdir),
            nf2ff,
            default_frequency_hz,
            executable=nf2ff_executable,
            timeout_s=nf2ff_timeout_s,
        )
        far_field = nf2ff_result["far_field"]
        gain_dbi = nf2ff_result["gain_dbi"]
    else:
        far_field = {
            "computed": False,
            "note": (
                "Far-field/gain pattern extraction needs the run's workdir "
                "and an 'nf2ff' recording-box definition (to invoke "
                "openEMS's separate nf2ff near-field-to-far-field "
                "post-processing tool) -- at least one wasn't given to "
                "parse_openems_output(), so nothing was computed. See "
                "simulation/openems.py's module docstring 'SCOPE OF THIS "
                "IMPLEMENTATION' for what's computed when they are."
            ),
        }
        gain_dbi = None

    return {
        "convergence": convergence,
        "s_parameters": s_parameters,
        "far_field": far_field,
        "gain_dbi": gain_dbi,
    }


def run_openems_simulation(
    geometry: dict[str, Any],
    fdtd: dict[str, Any] | None = None,
    timeout_s: int = 3600,
    executable: str | None = None,
    workdir: str | None = None,
    nf2ff_executable: str | None = None,
    nf2ff_timeout_s: int = 600,
) -> dict[str, Any]:
    """Generate an openEMS FDTD-XML file from structured geometry/materials/
    ports/mesh, run it via OpenemsSimulator, and parse convergence metadata
    plus S-parameter/far-field results tagged with SIMULATED provenance.
    S-parameters are real (FFT-computed from the run's port ProbeBox
    time-domain dumps) whenever those dump files are present in the run's
    workdir. Far-field/gain is real (issue #269) whenever `geometry['nf2ff']`
    names a recording box (see generate_openems_xml's docstring) -- this
    also switches the FDTD run's own extra_args to enable field/nf2ff dumps
    (dropping the default --disable-dumps, per this module's own
    Enable_Dumps citation), since a run that suppresses dumps would leave
    the NF2FF box with nothing to read. See this module's header comment
    "SCOPE OF THIS IMPLEMENTATION" for exactly what's covered either way.

    `nf2ff_executable`/`nf2ff_timeout_s` configure the SEPARATE `nf2ff`
    post-processing binary (default: the NF2FF_BIN env var, else "nf2ff") --
    independent of `executable`, which names the `openEMS` FDTD binary
    itself.

    See this module's header comment for the format-verification citations
    and the honest caveat: XML generation and log parsing are built to the
    documented/verified openEMS FDTD-XML and console-log formats, not to a
    real openEMS binary run in this environment.
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="openems_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    xml_file = work_dir / "model.xml"
    fdtd = fdtd or {}
    xml_file.write_text(generate_openems_xml(geometry, fdtd))

    nf2ff_def = geometry.get("nf2ff")
    job: dict[str, Any] = {
        "xml_file": str(xml_file),
        "workdir": str(work_dir),
        "timeout_s": timeout_s,
    }
    if nf2ff_def:
        # AC (issue #269): a run that requests an NF2FF box must not fall
        # back to the default --disable-dumps -- an empty extra_args list
        # restores the plain "openEMS <xml>" invocation with no flags (see
        # OpenemsSimulator.run()'s own docstring), so field/nf2ff dumps are
        # enabled for this run.
        job["extra_args"] = []

    simulator = OpenemsSimulator(executable=executable)
    result = simulator.run(job)
    parsed = parse_openems_output(
        result.outputs.get("stdout", ""),
        end_criteria=float(fdtd.get("end_criteria", 1e-5)),
        max_timesteps=int(fdtd.get("max_timesteps", 30000)),
        workdir=work_dir,
        ports=geometry.get("ports"),
        nf2ff=nf2ff_def,
        default_frequency_hz=geometry.get("frequency_hz"),
        nf2ff_executable=nf2ff_executable,
        nf2ff_timeout_s=nf2ff_timeout_s,
    )

    output: dict[str, Any] = {
        "provenance": result.provenance,
        "convergence": parsed["convergence"],
        "s_parameters": parsed["s_parameters"],
        "far_field": parsed["far_field"],
        "gain_dbi": parsed["gain_dbi"],
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "xml_file": str(xml_file),
    }
    touchstone_file = parsed["s_parameters"].get("touchstone_file")
    if touchstone_file:
        # Surfaced at top level (not just nested under s_parameters) so it
        # integrates with rf_tools.correlation.correlate_simulation_
        # measurement's own "touchstone_file"/"file" lookup, the same way
        # simulation/hfss.py's computed=True result already does.
        output["touchstone_file"] = touchstone_file
    return output
