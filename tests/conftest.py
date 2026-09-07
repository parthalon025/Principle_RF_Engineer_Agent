import os
import platform
import stat
import sys
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()


def make_fake_executable(tmp_path: Path, body: str, name: str = "fake_exe") -> Path:
    """Write `body` (Python source, with NO shebang line of its own) as a
    small stand-in for a real solver/geometry-tool binary, and return a
    path that can be handed straight to `subprocess.run()` as the literal
    executable to launch -- on POSIX *and* on native Windows.

    Every solver-adapter test in this suite fakes out a real binary this
    way, so it can drive the adapter's actual subprocess-invocation code
    (argument shape, exit-code handling, timeouts) without a real solver
    installed. Until issue #159, every one of these test doubles was a
    `#!/bin/sh`-shebang (or `#!{python}`-shebang) script with its
    executable bit set, launched directly as the subprocess target --
    which only ever worked because every environment that had run these
    tests (Linux CI) honors a shebang line for direct execution. Native
    Windows never does, for *any* interpreter: asked to start such a
    script directly, Windows tries to load it as a native PE `.exe` and
    fails with `OSError: [WinError 193] %1 is not a valid Win32
    application` -- regardless of which interpreter the shebang names.

    - On POSIX, this writes `body` behind a `#!{sys.executable}` shebang
      and sets the executable bit, exactly as every one of these fakes did
      before issue #159 -- the OS still resolves the shebang and launches
      it directly. Nothing changes here.
    - On native Windows, this instead writes `body` to a plain `.py` file
      and generates a `.bat` launcher next to it that explicitly invokes
      `sys.executable` on that file, forwarding every argument (`%*`).
      Windows' process launcher (`CreateProcess`) special-cases `.bat`/
      `.cmd` files -- it runs them through `cmd.exe` automatically -- so
      `subprocess.run([returned_path, *args])` launches the wrapper
      directly, with no `shell=True` and no change to any solver adapter's
      own subprocess-invocation code. The wrapper is the only thing that's
      platform-specific; `body` itself is ordinary, portable Python.
    """
    if platform.system() == "Windows":
        script = tmp_path / f"{name}.py"
        script.write_text(body)
        launcher = tmp_path / f"{name}.bat"
        launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n')
        return launcher
    else:
        script = tmp_path / name
        script.write_text(f"#!{sys.executable}\n" + body)
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return script


@pytest.fixture
def db_conn():
    """A real connection to the local Postgres, wrapped in a transaction
    that's rolled back on teardown so tests never leave data behind.

    Matches tests/test_touchstone.py's real-I/O-not-mocked philosophy,
    applied to the database instead of the filesystem.
    """
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
