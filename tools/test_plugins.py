#!/usr/bin/env python3
"""Runs every plugins-src/<name>/test.lua on the interpreter the keyboard ships.

WM Keyboard runs plugins on luaj 3.0.1, which is not the Lua you get from
Homebrew: strings are bytes, there is no utf8 library, and the UTF-8 codec
only knows the Basic Multilingual Plane. Testing on PUC Lua would pass things
that break on a phone, so this fetches the exact jar (or borrows it from the
Gradle cache when the app has been built on this machine) and runs each
plugin's tests under `java -cp luaj-jse-3.0.1.jar lua`.

A plugin opts in by having a test.lua next to its main.lua. The script is
run with the plugin folder as its working directory and must exit non-zero
on failure.

    python3 tools/test_plugins.py            # every plugin with a test.lua
    python3 tools/test_plugins.py math-mode  # just one
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "plugins-src"
CACHE_DIR = ROOT / ".cache"

LUAJ_VERSION = "3.0.1"
LUAJ_JAR = f"luaj-jse-{LUAJ_VERSION}.jar"
LUAJ_URL = f"https://repo1.maven.org/maven2/org/luaj/luaj-jse/{LUAJ_VERSION}/{LUAJ_JAR}"
LUAJ_SHA256 = "9b1f0a3e8f68427c6d74c2bf00ae0e6dbfce35994d3001fed4cef6ecda50be55"


def find_java() -> str:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / "java"
        if candidate.exists():
            return str(candidate)
    found = shutil.which("java")
    if found:
        return found
    studio = Path("/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/java")
    if studio.exists():
        return str(studio)
    sys.exit("java not found: set JAVA_HOME or install a JDK")


def find_jar() -> Path:
    gradle = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1" / "org.luaj" / "luaj-jse" / LUAJ_VERSION
    if gradle.is_dir():
        for hit in gradle.rglob(LUAJ_JAR):
            return hit
    cached = CACHE_DIR / LUAJ_JAR
    if cached.exists():
        return cached
    CACHE_DIR.mkdir(exist_ok=True)
    print(f"fetching {LUAJ_URL}")
    with urllib.request.urlopen(LUAJ_URL, timeout=60) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != LUAJ_SHA256:
        sys.exit(f"{LUAJ_JAR}: sha256 {digest} does not match the pinned {LUAJ_SHA256}")
    cached.write_bytes(data)
    return cached


def main(argv: list[str]) -> int:
    wanted = set(argv)
    folders = sorted(p for p in SOURCE_DIR.iterdir() if p.is_dir() and (p / "test.lua").exists())
    if wanted:
        missing = wanted - {p.name for p in folders}
        if missing:
            sys.exit(f"no test.lua for: {', '.join(sorted(missing))}")
        folders = [p for p in folders if p.name in wanted]
    if not folders:
        print("no plugin has a test.lua")
        return 0
    java = find_java()
    jar = find_jar()
    failed = 0
    for folder in folders:
        print(f"== {folder.name}")
        result = subprocess.run(
            [java, "-cp", str(jar), "lua", "test.lua"],
            cwd=folder,
            text=True,
            capture_output=True,
        )
        sys.stdout.write(result.stdout)
        if result.returncode != 0:
            sys.stdout.write(result.stderr)
            failed += 1
            print(f"   FAILED ({folder.name})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
