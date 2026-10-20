#!/usr/bin/env python3
"""Console menu for testing the MLEE assessment (the Windows start-menu entry).

Every option calls build.py or opens a file; nothing here does analysis.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
PDF = APP / "output" / "MLEE_Assessment_Report.pdf"
META = APP / "report" / "meta.tex"
INTERACTIVE = sys.stdin.isatty()

MENU = """
  MLEE Assessment  -  test console
  ----------------------------------------------------------------
   1  Run the analysis (all four tasks, about 30 s)
   2  Build the full report PDF (analysis + PDF + checks, about 1 min)
   3  Rebuild the PDF only (after changing the name or ID)
   4  Set the student name and ID printed on the report
   5  Open the report PDF
   6  Open the figures folder
   7  Show the headline results
   0  Exit
"""


def open_path(path: Path) -> None:
    if not path.exists():
        print(f"  Not created yet: {path}")
        return
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - opens with the default viewer
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def build(*args: str) -> int:
    cmd = [sys.executable, "-s", "-X", "utf8", str(APP / "build.py"), *args]
    return subprocess.run(cmd, cwd=APP).returncode


def latex_escape(text: str) -> str:
    special = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
               "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
               "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(special.get(ch, ch) for ch in text)


def meta_field(text: str, name: str) -> str:
    match = re.search(r"\\newcommand\{\\" + name + r"\}\{(.*)\}", text)
    return match.group(1) if match else "?"


def set_name_and_id() -> None:
    text = META.read_text(encoding="utf-8")
    print(f"  Currently: {meta_field(text, 'StudentName')}  /  "
          f"{meta_field(text, 'StudentID')}")
    for field, prompt in (("StudentName", "Student name"),
                          ("StudentID", "Student ID  ")):
        value = input(f"  {prompt} (Enter keeps the current one): ").strip()
        if value:
            pattern = r"(\\newcommand\{\\" + field + r"\}\{).*(\})"
            text = re.sub(pattern, lambda m: m.group(1) + latex_escape(value)
                          + m.group(2), text)
    META.write_text(text, encoding="utf-8", newline="\n")
    print("  Saved. Choose 3 to rebuild the PDF with the new details.")


def show_results() -> None:
    path = APP / "results.json"
    if not path.is_file():
        print("  No results yet: run option 1 first.")
        return
    r = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        ("Task 1  tuned tree test accuracy", f"{r['t1-tuned-acc']:.3f}"),
        ("Task 1  default tree test accuracy", f"{r['t1-default-acc']:.3f}"),
        ("Task 2  mixture weights", f"{r['t2-pi1']:.3f} / {r['t2-pi2']:.3f}"),
        ("Task 2  log-likelihood", f"{r['t2-loglik']:.2f}"),
        ("Task 3  PCs needed for 85 % variance", str(r["t3-k85"])),
        ("Task 4  FastICA |r| (worst source)", f"{r['t4-r-ica-min']:.4f}"),
        ("Task 4  PCA |r| (worst source)", f"{r['t4-r-pca-min']:.3f}"),
    ]
    for label, value in rows:
        print(f"  {label:<40} {value}")


def pause() -> None:
    if INTERACTIVE:
        input("\n  Press Enter to return to the menu ...")


def main() -> None:
    actions = {
        "1": lambda: build("--analysis-only", "--compare"),
        "2": lambda: build("--compare"),
        "3": lambda: build("--pdf-only"),
        "4": set_name_and_id,
        "5": lambda: open_path(PDF),
        "6": lambda: open_path(APP / "report" / "figures"),
        "7": show_results,
    }
    while True:
        print(MENU)
        try:
            choice = input("  Choose an option: ").strip()
        except EOFError:
            return
        if choice in ("0", "q", "exit"):
            return
        action = actions.get(choice)
        if action is None:
            print("  Please type one of the numbers shown.")
            continue
        try:
            action()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
        pause()


if __name__ == "__main__":
    main()
