#!/usr/bin/env python3
"""Checks every plugin in plugins-src/ and runs its tests.

WM Keyboard runs plugins on wm-python, its Rust port of PyMini (the small
Python Clink uses). PyMini is not CPython: strings are grapheme clusters,
there are no classes or `with`, and only a few modules exist. So the real
check is the real interpreter, through its command-line runner:

    cargo install --git https://github.com/wasi-master/WMKeyboard --rev <sha> wm-python-cli

For every plugin this script

1. lints main.py (and test.py) for Python that PyMini does not have,
2. renders it with stand-in `wm` and `ui` and touches every widget it shows,
   checking each tree against the host's caps (CPython, tools/pyplugin_host.py),
3. runs its test.py, if it has one, under `wm-python-cli test <folder>`.
   Without the CLI on PATH, test.py runs on CPython with the same stand-ins
   and a warning, which catches most mistakes but not the PyMini-only ones.

An API 5 plugin (the `wm` package) skips steps 1 and 2: the stand-ins model
API 4 only. It must have a test.py, and it needs the CLI.

A test.py imports `plugin_test`, which the runner provides: `read(name)`
returns a file from the plugin's folder and `load(name, wm, ui)` runs a plugin
file with the given `wm` and `ui` and returns its globals. A failing test
raises; the run then exits non-zero.

    python3 tools/test_plugins.py              # every plugin
    python3 tools/test_plugins.py math-mode    # just one
    python3 tools/test_plugins.py --cpython    # skip wm-python-cli even if installed
    python3 tools/test_plugins.py --require-cli  # fail when wm-python-cli is missing (CI)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "plugins-src"
CLI = "wm-python-cli"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pyplugin_host  # noqa: E402


def entry_of(folder: Path) -> Path:
    manifest = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    return folder / manifest.get("entry", "main.py")


def api_of(folder: Path) -> int:
    manifest = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    return manifest.get("apiVersion", 4)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plugins", nargs="*", help="folder names under plugins-src/")
    parser.add_argument("--cpython", action="store_true", help="run test.py on CPython even if the CLI is installed")
    parser.add_argument("--require-cli", action="store_true", help=f"fail if {CLI} is not on PATH")
    args = parser.parse_args(argv)

    folders = sorted(p for p in SOURCE_DIR.iterdir() if p.is_dir() and (p / "plugin.json").exists())
    if args.plugins:
        missing = set(args.plugins) - {p.name for p in folders}
        if missing:
            sys.exit(f"no such plugin: {', '.join(sorted(missing))}")
        folders = [p for p in folders if p.name in args.plugins]

    cli = None if args.cpython else shutil.which(CLI)
    if cli is None and args.require_cli:
        sys.exit(f"{CLI} is not on PATH")
    if cli is None and not args.cpython:
        print(f"warning: {CLI} not found; running test.py on CPython stand-ins "
              f"(install it with cargo, see this script's docstring)")

    failed = 0
    for folder in folders:
        print(f"== {folder.name}")
        problems: list[str] = []
        entry = entry_of(folder)
        # API 5 (the wm package: classes, `with`, several modules) is past
        # what the CPython stand-ins model, so only the real interpreter
        # checks it.
        api5 = api_of(folder) == 5
        test = folder / "test.py"
        if not entry.is_file():
            problems.append(f"{entry.relative_to(ROOT)} is missing")
        elif api5:
            if not test.is_file():
                problems.append("an API 5 plugin needs a test.py, run under wm-python-cli")
            elif cli is None:
                problems.append(f"an API 5 plugin is tested only under {CLI}, which is not on PATH")
        else:
            problems += pyplugin_host.check_subset(entry)
            if test.is_file():
                problems += pyplugin_host.check_subset(test, host_globals=False)
            if not problems:
                problems += pyplugin_host.smoke(folder)
        for line in problems:
            print(f"   {line}")

        test_failed = False
        if test.is_file() and not problems:
            if cli:
                result = subprocess.run([cli, "test", str(folder)], text=True, capture_output=True)
                sys.stdout.write(result.stdout)
                if result.returncode != 0:
                    sys.stdout.write(result.stderr)
                    test_failed = True
            else:
                test_failed = pyplugin_host.run_test(folder) != 0
        if problems or test_failed:
            failed += 1
            print(f"   FAILED ({folder.name})")
        elif not test.is_file():
            print("   ok (lint and smoke; no test.py)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
