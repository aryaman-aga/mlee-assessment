#!/usr/bin/env python3
"""Build the MLEE report on any platform: data check -> analysis -> PDF -> QA.

    python build.py                  full build: analysis, PDF and checks
    python build.py --analysis-only  run the four tasks only (figures, results)
    python build.py --pdf-only       recompile the PDF from the last analysis
    python build.py --compare        also compare results.json with the
                                     reference run for this platform

In the Windows installation this file lives in <install>\\app, next to the
bundled Python (<install>\\python), Tectonic (<install>\\tectonic) and an
offline TeX cache (<install>\\texcache); all three are found automatically.
Environment overrides: MLEE_TECTONIC, MLEE_TEXCACHE, MLEE_REQUIRE_OFFLINE=1
(fail instead of downloading TeX files), MLEE_STRICT_COMPARE=1 (fail when
--compare finds a difference).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parent
INSTALL = APP.parent
DEFAULT_PDF = APP / "output" / "MLEE_Assessment_Report.pdf"
REL_TOL = 1e-6  # cross-platform tolerance for the reference comparison


def say(message: str) -> None:
    print(f"[mlee] {message}", flush=True)


def fail(message: str) -> None:
    print(f"[mlee] ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def verify_data() -> None:
    sums = (APP / "data" / "SHA256SUMS").read_text(encoding="utf-8")
    for line in sums.splitlines():
        digest, name = line.split()
        path = APP / "data" / name
        if not path.is_file():
            fail(f"missing data file {path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            fail(f"{path.name} does not match its recorded SHA-256")
    say("data files verified (SHA-256)")


def python_cmd(script: str, *args: str) -> list[str]:
    # -s: ignore the user's own site-packages, so only the bundled ones are used
    return [sys.executable, "-s", "-X", "utf8", script, *args]


def run_analysis() -> None:
    say("running the analysis for all four tasks (about 30 s) ...")
    start = time.perf_counter()
    log = APP / "build" / "analysis.log"
    log.parent.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", MPLBACKEND="Agg")
    with log.open("w", encoding="utf-8", newline="\n") as handle:
        proc = subprocess.run(python_cmd("mlee_assessment.py"), cwd=APP,
                              stdout=handle, stderr=subprocess.STDOUT, env=env)
    if proc.returncode:
        print(log.read_text(encoding="utf-8")[-4000:])
        fail(f"the analysis failed; full log in {log}")
    say(f"analysis finished in {time.perf_counter() - start:.0f} s: "
        f"figures in report/figures, numbers in results.json")


def find_tectonic() -> str:
    for candidate in (os.environ.get("MLEE_TECTONIC"),
                      INSTALL / "tectonic" / "tectonic.exe",
                      shutil.which("tectonic")):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    fail("Tectonic was not found (set MLEE_TECTONIC or put it on PATH)")


def build_pdf(out: Path, online: bool) -> None:
    tectonic = find_tectonic()
    env = dict(os.environ)
    cache = Path(os.environ.get("MLEE_TEXCACHE", INSTALL / "texcache"))
    offline = cache.is_dir() and not online
    if cache.is_dir():
        env["TECTONIC_CACHE_DIR"] = str(cache)
    cmd = [tectonic, "--keep-logs", "--outdir", str(APP / "build"), "main.tex"]
    if offline:
        cmd.insert(1, "--only-cached")
    say("typesetting the report PDF"
        + (" with the offline TeX cache ..." if offline else " ..."))

    def typeset(command):
        return subprocess.run(command, cwd=APP / "report", env=env,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    proc = typeset(cmd)
    if proc.returncode and offline:
        if os.environ.get("MLEE_REQUIRE_OFFLINE") == "1":
            print(proc.stdout[-3000:], proc.stderr[-3000:], sep="\n")
            fail("the offline TeX cache is incomplete")
        say("offline TeX cache is incomplete; retrying with downloads on")
        cmd.remove("--only-cached")
        proc = typeset(cmd)
    if proc.returncode:
        print(proc.stdout[-3000:], proc.stderr[-3000:], sep="\n")
        fail("the PDF build failed; see app/build/main.log")
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(APP / "build" / "main.pdf", out)
    say(f"PDF written to {out}")


def run_qa(out: Path) -> None:
    say("checking the PDF ...")
    if subprocess.run(python_cmd("qa_check.py", str(out)), cwd=APP).returncode:
        fail("one or more QA checks failed (listed above)")


def diff_results(ref: dict, new: dict) -> tuple[list, int]:
    """Values that differ beyond REL_TOL, walking nested lists and dicts."""
    diffs, count = [], 0

    def walk(a, b, key):
        nonlocal count
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(a.keys() | b.keys()):
                walk(a.get(k), b.get(k), f"{key}.{k}" if key else k)
        elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{key}[{i}]")
        else:
            count += 1
            numeric = all(isinstance(v, (int, float))
                          and not isinstance(v, bool) for v in (a, b))
            same = (math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-12)
                    if numeric else a == b)
            if not same:
                diffs.append((key, a, b))

    walk(ref, new, "")
    return diffs, count


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_reference() -> None:
    """Compare results.json with the reference run for this platform.

    Fully grown decision trees break exact ties between candidate splits
    differently on different CPU architectures, so the Windows (x64) build
    has its own reference; it differs from the macOS submission run only in
    the unconstrained-tree experiments of Task 1.
    """
    mac = APP / "reference" / "results.json"
    win = APP / "reference" / "results-windows.json"
    ref = win if sys.platform == "win32" and win.is_file() else mac
    if not ref.is_file():
        say("no reference results found; comparison skipped")
        return
    label = "Windows" if ref == win else "macOS"
    new = load(APP / "results.json")
    diffs, count = diff_results(load(ref), new)
    if not diffs:
        say(f"results match the {label} reference run: {count} values "
            f"within a relative tolerance of {REL_TOL:g}")
        if ref == win and mac.is_file():
            n = len(diff_results(load(mac), new)[0])
            say(f"(vs the macOS submission run: {n} values differ, all from "
                f"the unconstrained-tree experiments; see README)")
        return
    say(f"{len(diffs)} of {count} values differ from the {label} reference run:")
    for key, a, b in diffs[:15]:
        print(f"         {key}: reference {a!r}, this run {b!r}")
    if os.environ.get("MLEE_STRICT_COMPARE") == "1":
        fail("results differ from the reference run")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--analysis-only", action="store_true",
                      help="run the four tasks, skip the PDF")
    mode.add_argument("--pdf-only", action="store_true",
                      help="recompile the PDF from the last analysis")
    parser.add_argument("--compare", action="store_true",
                        help="compare results.json with the reference run")
    parser.add_argument("--online", action="store_true",
                        help="let Tectonic download TeX files (fills the cache)")
    parser.add_argument("--out", type=Path, default=DEFAULT_PDF,
                        help=f"where to write the PDF (default {DEFAULT_PDF})")
    args = parser.parse_args()

    verify_data()
    if not args.pdf_only:
        run_analysis()
        if args.compare:
            compare_reference()
    if args.analysis_only:
        return
    out = args.out.resolve()
    build_pdf(out, args.online)
    run_qa(out)
    say("all done")


if __name__ == "__main__":
    main()
