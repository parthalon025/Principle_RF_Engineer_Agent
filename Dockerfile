# Runs the whole program (agent, mcp_server, tests) plus as many of the
# free/OSS solver/geometry binaries as this image can genuinely install, on
# Linux -- sidestepping the Windows-only blockers several of them have (no
# native Windows build at all for MEEP; no-admin-rights friction for
# Chocolatey; 7z-only Windows releases with no built-in extractor). See
# docs/FREE_AND_OPEN_SOURCE_TOOLING.md for what each tool is and why it's
# here, and README.md's "Optional: solvers and external tools" section for
# the per-tool license/fit notes this Dockerfile doesn't repeat.
#
# Every apt package name and build recipe below was verified against real
# primary sources (a real Ubuntu 24.04 container's own `apt-cache show`
# byte content, or the upstream project's own current docs/CI/source) before
# being added -- see this repo's own citation-precision convention. Several
# things that LOOKED right turned out wrong on verification and are called
# out inline so nobody re-introduces them:
#   - `nec2c` (apt) is a DIFFERENT project from `nec2++` (tmolteno/necpp,
#     what simulation/nec2pp.py is built against) with an incompatible CLI.
#   - `meep`/`openems`/`qucs`/`freecad` (bare, no PPA) all show up as a
#     recognized apt package NAME with ZERO bytes of real package data --
#     `apt-cache show X > /dev/null 2>&1 && echo AVAILABLE` reports exit 0
#     for these hollow entries even though there is nothing to install.
#     Always check real byte content, not just exit code.
#
# Solver layers are ordered cheapest/fastest-to-verify first, most expensive
# last, so a mistake surfaces in seconds/minutes rather than after an
# hour-plus Xyce/Palace compile. They sit BEFORE the application COPY/uv
# sync steps specifically so editing app code never invalidates these
# (expensive) build caches.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# --- apt-installable solvers -------------------------------------------
# pandoc, file, and poppler-utils are not solvers -- they're apt-installable
# runtime dependencies of .claude/skills/arxiv-doc-builder's PDF tier
# (knowledge/sourcing/arxiv.py and, since ticket #219,
# knowledge/sourcing/patent.py both shell out into it via `uv run
# --project`): pandoc does the LaTeX-source-to-Markdown conversion (its
# happy path, per that skill's SKILL.md), fetch_paper.py's own
# format-detection shells to `file --brief` on the downloaded arXiv source
# archive, and poppler-utils supplies `pdftoppm`/`pdfinfo` -- the external
# binaries `pdf2image` (arxiv_doc_builder/pdf_image_lib.py's
# `convert_from_path`, used by both arXiv's own vision fallback and
# patent.py's scanned-patent vision route) shells out to itself; without it
# `convert_from_path` raises `PDFInfoNotInstalledError` before rendering a
# single page (confirmed directly in this ticket's own sandbox, which also
# lacked poppler-utils). tar/gzip (the other two external commands
# fetch_paper.py invokes) are already part of ubuntu:24.04's base image,
# unlike these three, which are not. Placed in this same general apt block
# as gerbv (another non-solver runtime dependency already living here)
# rather than a dedicated layer, since all are small, fast apt installs.
# Standard Ubuntu universe packages, not independently verified against a
# live build the way this file's other, larger layers below are (see this
# file's own top comment) -- if any name turns out wrong, `apt-cache show
# pandoc`/`apt-cache show file`/`apt-cache show poppler-utils` in a real
# ubuntu:24.04 container is the first thing to check, per that same top
# comment's own "always check real byte content" warning.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    git \
    software-properties-common \
    build-essential \
    cmake \
    pkg-config \
    gfortran \
    flex \
    bison \
    gperf \
    dos2unix \
    libfl-dev \
    ngspice \
    kicad \
    gmsh \
    gerbv \
    pandoc \
    file \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# FreeCAD ships NO installable candidate at all in default Ubuntu 24.04/26.04
# repos (confirmed: 0 bytes from `apt-cache show freecad`) -- the
# FreeCAD-maintainers PPA is the documented fix. Using -stable, not -daily,
# for build reproducibility.
RUN add-apt-repository -y ppa:freecad-maintainers/freecad-stable \
    && apt-get update \
    && apt-get install -y --no-install-recommends freecad \
    && rm -rf /var/lib/apt/lists/*

# The PPA installs the headless console binary as lowercase `freecadcmd`;
# geometry/freecad_curved.py's FREECAD_BIN default is the mixed-case
# `FreeCADCmd` (matching FreeCAD's own Windows/macOS naming) -- Linux
# binary lookups are case-sensitive, so without this symlink the adapter's
# default silently fails to find it. Confirmed by actually running `which
# FreeCADCmd` vs `which freecadcmd` in the built image, not assumed.
RUN ln -s /usr/bin/freecadcmd /usr/bin/FreeCADCmd

# --- NEC2++ (tmolteno/necpp) ---------------------------------------------
# Self-contained CMake project, Eigen bundled, no external library deps.
# -DNECPP_BUILD_TESTS=OFF skips a Catch2 FetchContent network pull this
# repo doesn't need (only the CLI binary matters here). CLI confirmed by
# reading src/nec2cpp.cpp directly: "-i <file> -o -" (space-separated,
# "-o -" for stdout) matches simulation/nec2pp.py's invocation exactly.
# Pinned to v2.3.4 (issue #410) -- the newest tag as of this pin, confirmed
# to exist via `git ls-remote --tags`. Previously unpinned, so two builds
# on different days could silently produce different binaries.
RUN git clone --branch v2.3.4 --depth 1 https://github.com/tmolteno/necpp.git /opt/necpp \
    && cmake -B /opt/necpp/build -S /opt/necpp -DCMAKE_BUILD_TYPE=Release -DNECPP_BUILD_TESTS=OFF \
    && cmake --build /opt/necpp/build -j$(nproc) \
    && cmake --install /opt/necpp/build \
    && rm -rf /opt/necpp \
    && nec2++ -h 2>&1 | head -3

# --- Elmer FEM (ElmerSolver + ElmerGrid) ---------------------------------
# No apt/deb package exists anywhere for Elmer -- source build is the only
# route. This exact recipe was docker-built and run end to end during
# research for this Dockerfile (ElmerSolver -v / ElmerGrid confirmed
# working). gmsh is already installed above. GUI (ElmerGUI/Qt/VTK/ParaView)
# deliberately excluded -- headless ElmerSolver+ElmerGrid only.
# Pinned to release-26.2.1 (issue #410) -- the newest release tag as of
# this pin, confirmed to exist via `git ls-remote --tags`. Previously
# unpinned (`--depth 1` with no branch/tag), so two builds on different
# days could silently produce different binaries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenmpi-dev \
    libblas-dev \
    liblapack-dev \
    libmumps-dev \
    libparmetis-dev \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --branch release-26.2.1 --depth 1 https://github.com/ElmerCSC/elmerfem.git /opt/elmerfem \
    && cmake -S /opt/elmerfem -B /opt/elmerfem/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
       -DWITH_OpenMP:BOOLEAN=TRUE -DWITH_MPI:BOOLEAN=TRUE -DWITH_Mumps:BOOL=TRUE -DWITH_ELMERGUI:BOOL=FALSE -DWITH_LUA:BOOL=TRUE \
    && cmake --build /opt/elmerfem/build -j$(nproc) \
    && cmake --install /opt/elmerfem/build \
    && rm -rf /opt/elmerfem \
    && ElmerSolver -v 2>&1 | head -5 \
    && ElmerGrid 2>&1 | head -3

# --- Qucs-S / qucsator_rf -------------------------------------------------
# NOT the apt `qucs` package (the old, unrelated pre-fork project) and NOT
# a GUI build -- pure console CMake project, confirmed via src/ucs.cpp's
# main(): "-i <file> -o <file>" CLI, no Qt/GUI deps. flex/bison/gperf/
# dos2unix already installed above.
RUN git clone --branch 1.0.7 --depth 1 https://github.com/ra3xdh/qucsator_rf.git /opt/qucsator_rf \
    && cmake -S /opt/qucsator_rf -B /opt/qucsator_rf/build -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /opt/qucsator_rf/build -j$(nproc) \
    && cmake --install /opt/qucsator_rf/build \
    && rm -rf /opt/qucsator_rf \
    && qucsator_rf --version

# --- gprMax ---------------------------------------------------------------
# No PyPI/conda-forge package exists (pypi.org/pypi/gprMax/json 404s) --
# always a real Cython compile. Isolated in its own venv (Ubuntu 24.04's
# system Python is PEP-668 externally-managed, so a bare pip install would
# be refused). requirements.txt staged first (numpy/Cython) so the
# --no-build-isolation install of gprMax itself, whose setup.py does a bare
# `import numpy` at parse time, can actually see them. simulation/gprmax.py
# invokes "<python> -m gprMax <input_file>" -- no standalone binary, point
# GPRMAX_PYTHON at this venv's interpreter.
#
# Pinned to commit 950d0e1976d344e4509251b7ebe385e5cd0836e9 (issue #459),
# a specific commit SHA rather than the newest tag (v.3.1.7, Jan 2024):
# that tag's own requirements.txt is a `pip freeze` dump of a Jupyter dev
# environment -- hundreds of exact-pinned, now-ancient packages, and it
# even lists "gprMax==3.1.4" as one of its own dependencies, which does
# not exist on PyPI -- `pip install -r requirements.txt` against it fails
# outright, confirmed by actually running it. The pinned commit's
# requirements.txt (floors, not exact pins, explicitly "gprMax supports
# NumPy 2.x") was confirmed end to end instead: a fresh venv install of
# that requirements.txt followed by `pip install --no-build-isolation
# <checkout>` succeeded, producing a working `python -m gprMax --help`.
# `git fetch --depth 1 origin <sha>` (rather than `git clone --branch`,
# which only resolves branch/tag names, not arbitrary commits) shallow-
# fetches this exact commit -- confirmed GitHub serves it, since GitHub
# advertises recent commits for direct shallow fetch.
RUN apt-get update && apt-get install -y --no-install-recommends python3-dev python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/gprmax-venv \
    && /opt/gprmax-venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && git init -q /opt/gprMax \
    && git -C /opt/gprMax remote add origin https://github.com/gprMax/gprMax.git \
    && git -C /opt/gprMax fetch --depth 1 origin 950d0e1976d344e4509251b7ebe385e5cd0836e9 \
    && git -C /opt/gprMax checkout FETCH_HEAD \
    && /opt/gprmax-venv/bin/pip install --no-cache-dir -r /opt/gprMax/requirements.txt \
    && /opt/gprmax-venv/bin/pip install --no-cache-dir --no-build-isolation /opt/gprMax \
    && rm -rf /opt/gprMax \
    && /opt/gprmax-venv/bin/python -m gprMax --help
ENV GPRMAX_PYTHON=/opt/gprmax-venv/bin/python3

# --- MEEP (pymeep, via conda-forge) ---------------------------------------
# The ONLY reliable Linux install path -- confirmed no ubuntu:24.04 apt
# package (python3-meep exists on jammy/Debian, NOT noble), no PyPI
# "meep"/"pymeep" (PyPI's "meep" is an unrelated squatted package). MEEP is
# imported as a library ("import meep"), never invoked as a CLI --
# simulation/meep.py's _import_meep() matches this exactly.
# Pinned to release 26.7.2-0 (issue #410) -- the newest release as of this
# pin; the asset URL, versioned tag included, was confirmed to resolve
# (302 to the real download) before pinning. Previously downloaded via
# `/releases/latest/download/`, which always resolves to whatever is
# current on build day, so two builds on different days could silently
# install different conda/Python/pymeep versions.
RUN wget -q https://github.com/conda-forge/miniforge/releases/download/26.7.2-0/Miniforge3-26.7.2-0-Linux-x86_64.sh -O /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm /tmp/miniforge.sh \
    && /opt/conda/bin/conda create -y -n mp -c conda-forge pymeep \
    && /opt/conda/bin/conda clean -afy \
    && /opt/conda/envs/mp/bin/python -c "import meep"
ENV MEEP_PYTHON=/opt/conda/envs/mp/bin/python3

# --- OpenParEM3D (prebuilt) ------------------------------------------------
# The project's own release explicitly targets "Ubuntu 24.04 LTS" with no
# further package installs needed for its bundled MPI/PETSc/MFEM/HYPRE/
# METIS/MUMPS/ScaLAPACK stack -- only the base-image runtime libs it does
# NOT bundle (libgfortran/libgomp/libquadmath) need to come from apt.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgfortran5 libgomp1 libquadmath0 \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL -o /tmp/openparem.tar.gz https://github.com/OpenParEM/OpenParEM/releases/download/2.1.0/OpenParEM-2.1.0-bin.tar.gz \
    && mkdir -p /opt/openparem \
    && tar -xzf /tmp/openparem.tar.gz -C /opt/openparem \
    && ln -s /opt/openparem/OpenParEM-2.1.0 /opt/openparem/OpenParEM \
    && rm /tmp/openparem.tar.gz \
    && (LD_LIBRARY_PATH="/opt/openparem/OpenParEM/lib:/opt/openparem/OpenParEM/lib64:${LD_LIBRARY_PATH}" \
        ldd /opt/openparem/OpenParEM/bin/OpenParEM3D.bin | grep -i "not found" && exit 1 || true)
ENV PATH="/opt/openparem/OpenParEM/bin:/opt/openparem/OpenParEM/scripts:${PATH}"
ENV OPENPAREM3D_BIN=OpenParEM3D

# --- openEMS + CSXCAD ------------------------------------------------------
# No Ubuntu/Debian package, PPA, conda, snap, flatpak, or official Docker
# image exists for this -- source build via the project's own
# update_openEMS.sh orchestrator (confirmed non-interactive: no `read`, no
# `sudo` anywhere in its source) is the only route. MUST be a full,
# non-shallow `--recursive` clone -- CMake calls `git describe --tags` for
# versioning and fails on a shallow clone (--branch alone, with no
# --depth, stays non-shallow -- it only narrows which ref is fetched).
# Pinned to v0.0.36 (issue #410) -- the newest non-release-candidate tag
# as of this pin (v0.37.0-rc1/rc2 exist but are pre-release); every
# submodule (AppCSXCAD, CSXCAD, CTB, QCSXCAD, fparser, hyp2mat, openEMS)
# was confirmed to resolve cleanly at this ref via an actual `git clone
# --branch v0.0.36 --recursive`. Previously unpinned, so two builds on
# different days -- and their submodules, each on their own default
# branch -- could silently produce different binaries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-dev libtinyxml-dev libboost-all-dev libcgal-dev libvtk9-dev \
    python3-pip python3-setuptools python3-setuptools-scm cython3 \
    python3-numpy python3-h5py python3-matplotlib \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --branch v0.0.36 --recursive https://github.com/thliebig/openEMS-Project.git /opt/openEMS-Project \
    && cd /opt/openEMS-Project && ./update_openEMS.sh /opt/openEMS --python --disable-GUI --python-venv-mode=disable --python-use-network=disable --skip-dep-check \
    && cd / && rm -rf /opt/openEMS-Project
ENV PATH="/opt/openEMS/bin:${PATH}"

# --- Palace (awslabs/palace) -----------------------------------------------
# No official prebuilt image exists anywhere (Docker Hub/ghcr.io/public ECR
# all checked, none found) -- Palace's own CMake superbuild compiles MFEM,
# libCEED, GSLIB, METIS/ParMETIS, Hypre, SuperLU_DIST, SLEPc+PETSc,
# LIBXSMM, MAGMA and SUNDIALS from source itself as part of one
# `cmake --build`. gfortran is a HARD requirement despite docs calling it
# "optional" -- without it, SuperLU_DIST/SLEPc/PETSc silently lose
# Fortran-dependent pieces and the build fails with "need at least one
# sparse direct solver". This is the single most expensive layer here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 libopenmpi-dev openmpi-bin libopenblas-dev libunwind-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --branch v0.17.0 --depth 1 https://github.com/awslabs/palace.git /opt/palace-src \
    && cmake -S /opt/palace-src -B /opt/palace-src/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/palace \
    && cmake --build /opt/palace-src/build -j$(nproc) \
    && rm -rf /opt/palace-src \
    && ln -s /opt/palace/bin/palace /usr/local/bin/palace \
    && palace --help 2>&1 | head -5

# --- Xyce (Sandia National Laboratories) -----------------------------------
# No Ubuntu/Docker binary exists anywhere, official or current-community --
# a real three-tier build: SuiteSparse's AMD subset (Ubuntu's apt
# libsuitesparse-dev is 7.6.1, below Xyce's 7.8.3 floor) -> a trimmed
# serial Trilinos 14.4 (using Xyce's OWN initial-cache file, not hand-picked
# flags) -> Xyce itself. Serial (no MPI) matches simulation/xyce.py's
# direct, non-mpirun invocation. libfftw3-dev deliberately omitted: it only
# enables Harmonic Balance (.HB), which this repo's adapter never emits.
# The binary must be literally named "Xyce" (capital X) for XYCE_BIN's
# default to find it via PATH.
RUN git clone --branch Release-7.10.0 --depth 1 https://github.com/Xyce/Xyce.git /src/Xyce \
    && git clone --branch v7.8.3 --depth 1 https://github.com/DrTimothyAldenDavis/SuiteSparse.git /src/SuiteSparse \
    && git clone --branch trilinos-release-14-4-branch --depth 1 https://github.com/trilinos/Trilinos.git /src/Trilinos \
    && cmake -S /src/SuiteSparse -B /build/SuiteSparse -D CMAKE_INSTALL_PREFIX=/opt/xyce-tpls \
       -D SUITESPARSE_ENABLE_PROJECTS='suitesparse_config;amd' -D CMAKE_BUILD_TYPE=Release \
    && cmake --build /build/SuiteSparse -j$(nproc) --target install \
    && cmake -C /src/Xyce/cmake/trilinos/trilinos-base.cmake -S /src/Trilinos -B /build/Trilinos \
       -D CMAKE_INSTALL_PREFIX=/opt/xyce-tpls -D CMAKE_BUILD_TYPE=Release \
       -D CMAKE_C_COMPILER=gcc -D CMAKE_CXX_COMPILER=g++ -D CMAKE_Fortran_COMPILER=gfortran \
       -D AMD_LIBRARY_DIRS=/opt/xyce-tpls/lib -D AMD_INCLUDE_DIRS=/opt/xyce-tpls/include/suitesparse \
    && cmake --build /build/Trilinos -j$(nproc) --target install \
    && cmake -S /src/Xyce -B /build/Xyce -D CMAKE_INSTALL_PREFIX=/opt/xyce -D CMAKE_BUILD_TYPE=Release -D Trilinos_ROOT=/opt/xyce-tpls \
    && cmake --build /build/Xyce -j$(nproc) --target install \
    && rm -rf /src/Xyce /src/SuiteSparse /src/Trilinos /build \
    && /opt/xyce/bin/Xyce -v
ENV PATH="/opt/xyce/bin:${PATH}"

# --- application ------------------------------------------------------------
# uv manages the project's own Python dependencies (see pyproject.toml,
# requires-python >=3.12) and its own Python interpreter -- no system
# python3-dev/pip juggling needed. Placed after every solver layer above so
# editing app code / pyproject.toml never invalidates those (expensive)
# build caches.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml uv.lock ./
# --extra kicad: this image installs the EXTERNAL KiCad tool (via apt above),
# but a bare `uv sync` installs no optional extras at all, so kicad-python
# (kipy) -- what simulation/kicad_gerber2ems.py imports to drive it -- was
# absent inside a container that had the KiCad binary itself. gdstk (what
# geometry/unit_cell.py needs) used to need its own `--extra geometry` here
# too, before issue #348 made it a hard `dependencies` entry instead (it has
# no license/hardware gate of its own, so a bare `uv sync` now installs it
# unconditionally) -- `--extra geometry` no longer exists as an extras group
# and passing it here would fail the build. Deliberately NOT --extra hfss
# (licence-confined workstation only, ADR-0012) or --extra ltspice (LTspice
# is Windows freeware and is not in this image), so those two stay absent on
# purpose rather than by omission.
RUN uv sync --frozen --no-install-project --extra kicad
COPY . .
RUN uv sync --frozen --extra kicad

# docker-compose.yml's `app` service bind-mounts the live repo over /app
# AND puts /app/.venv on its own separate named volume (app_venv) -- so the
# .venv built above, inside the image, gets shadowed by that (initially
# EMPTY) named volume the moment the container starts under compose. This
# entrypoint re-runs `uv sync` on every start to repopulate it -- fast/
# idempotent once the lockfile hasn't changed, and makes `docker compose
# run app <cmd>` genuinely work with no manual first-run step. A plain
# `docker run rf-agent:full` (no compose, no bind mount) still has the
# image's own baked .venv already in place, so this is a no-op there too.
COPY <<'EOF' /entrypoint.sh
#!/bin/sh
set -e
uv sync --frozen --no-progress --extra kicad
exec "$@"
EOF
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uv", "run", "python", "-m", "mcp_server.server"]
