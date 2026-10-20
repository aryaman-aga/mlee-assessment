#!/usr/bin/env python3
"""Automated checks on the finished report (run by build.sh).

    python qa_check.py ../MLEE_Assessment_Report.pdf

Fails (exit 1) unless the PDF satisfies the submission rules and is
consistent with the analysis that produced it.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
MAX_PAGES = 6
A4 = (595, 842)
# task-sheet limits on the written discussions
SENTENCES = {"task1": (3, 4), "task2": (2, 3), "task4": (3, 4)}

failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def results_tex() -> dict[str, str]:
    text = (ROOT / "report/generated/results.tex").read_text(encoding="utf-8")
    pat = re.compile(r"\\csname r@(.+?)\\endcsname\{(.*)\}$", re.M)
    return dict(pat.findall(text))


def plain(tex: str, values: dict[str, str]) -> str:
    """Rough LaTeX -> text, enough to count sentences reliably."""
    tex = re.sub(r"%.*", "", tex)
    tex = re.sub(r"\\R\{([^}]*)\}", lambda m: values[m.group(1)], tex)
    tex = re.sub(r"\$[^$]*\$", "M", tex)
    tex = re.sub(r"\\(?:ref|eqref|cite)\{[^}]*\}", "1", tex)
    tex = re.sub(r"\\[a-zA-Z]+\*?(\[[^]]*\])?", "", tex)
    tex = tex.replace("~", " ").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", tex).strip()


def count_sentences(text: str) -> int:
    return len(re.findall(r"[.!?](?=\s+[A-Z(]|\s*$)", text))


def main(pdf_path: str) -> None:
    doc = pymupdf.open(pdf_path)
    values = results_tex()
    main_tex = (ROOT / "report/main.tex").read_text(encoding="utf-8")
    text = "\n".join(page.get_text() for page in doc).replace("\u2212", "-")

    print("Submission rules")
    check(doc.page_count <= MAX_PAGES, f"at most {MAX_PAGES} pages",
          f"{doc.page_count} pages")
    sizes = {(round(p.rect.width), round(p.rect.height)) for p in doc}
    check(sizes == {A4}, "every page is A4 (595 x 842 pt)", str(sizes))

    print("Fonts")
    fonts = {}
    for page in doc:
        for xref, ext, ftype, base, *_ in page.get_fonts(full=True):
            fonts[xref] = (ext, ftype, base.split("+")[-1])
    not_embedded = [b for e, _, b in fonts.values() if e == "n/a"]
    check(not not_embedded, "all fonts embedded", ", ".join(not_embedded))
    mislabelled = [b for x, (e, t, b) in fonts.items() if t == "TrueType"
                   and doc.extract_font(x)[3][:4] == b"OTTO"]
    check(not mislabelled, "no CFF font inside a TrueType slot",
          ", ".join(mislabelled))
    fallback = sorted({b for _, _, b in fonts.values()
                       if re.search(r"DejaVu|Helvetica|Arial|Courier", b)})
    check(not fallback, "no fallback fonts", ", ".join(fallback))
    families = sorted({re.sub(r"-(Identity-H|Regular|Roman|Bold|Italic"
                              r"|BoldItalic|Semibold)+$", "", b)
                       for _, _, b in fonts.values()})
    print(f"         families: {', '.join(families)}")

    print("LaTeX log")
    log = (ROOT / "build/main.log").read_text(encoding="utf-8", errors="replace")
    check("Missing character" not in log, "no missing glyphs")
    over = [float(x) for x in re.findall(r"Overfull \\[hv]box \((\d+\.?\d*)pt", log)]
    check(all(x <= 1.0 for x in over), "no overfull box above 1 pt",
          f"worst {max(over):.1f} pt" if over else "")
    check("undefined" not in log.lower() and "??" not in text,
          "all references resolved")

    print("Consistency with the analysis")
    body = re.sub(r"(?<!\\)%.*", "", main_tex)  # ignore comments
    keys = sorted(set(re.findall(r"\\R\{([^}]+)\}", body)))
    numeric = [k for k in keys if re.fullmatch(r"[-+]?[\d,]*\.?\d+", values[k])]
    missing = [k for k in numeric if values[k].lstrip("+") not in text]
    check(not missing, f"{len(numeric)} quoted numbers found in the PDF text",
          ", ".join(f"{k}={values[k]}" for k in missing[:6]))
    spec = importlib.util.spec_from_file_location("m", ROOT / "mlee_assessment.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    stale = [name for name, tex in m.render_snippets().items()
             if (ROOT / f"report/generated/{name}.tex").read_text(encoding="utf-8") != tex]
    check(not stale, "listings byte-identical to the current script",
          ", ".join(stale))

    print("Written answers")
    for task, (lo, hi) in SENTENCES.items():
        block = re.search(rf"% BEGIN discussion-{task}\n(.*?)% END discussion-{task}",
                          main_tex, re.S)
        n = count_sentences(plain(block.group(1), values)) if block else 0
        check(lo <= n <= hi, f"{task} discussion has {lo}-{hi} sentences",
              f"{n} sentences")

    print()
    if failures:
        print(f"QA FAILED: {len(failures)} check(s): {', '.join(failures)}")
        sys.exit(1)
    print(f"QA passed: {doc.page_count} pages, {pdf_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT.parent / "MLEE_Assessment_Report.pdf"))
