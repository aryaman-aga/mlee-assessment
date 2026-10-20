# MLEE Course Assessment: source for the report

The submission is `../MLEE_Assessment_Report.pdf` (5 A4 pages; the limit is 6).
Everything in it is generated from this folder.

| File | Role |
|---|---|
| `mlee_assessment.py` | All four tasks. Writes the figures, every number quoted in the text, and the highlighted code listings. |
| `report/main.tex` | Layout and prose. Numbers appear as `\R{key}` macros filled from `report/generated/results.tex`. |
| `report/meta.tex` | Name and student ID shown in the title block and running header. |
| `qa_check.py` | Checks on the finished PDF: page count and size, embedded fonts, numbers match the analysis, listings match the script, discussion sentence counts. |
| `build.sh` | macOS wrapper: sets up `.venv` and the data, then runs `build.py`. |
| `data/` | The two downloaded CSVs plus `SHA256SUMS`. The breast-cancer data ships with scikit-learn. |
| `fonts/` | Lato TTFs (SIL OFL), taken from the Tectonic TeX bundle so the figures use the report's sans-serif font. |
| `build.py` | Cross-platform build driver used by `build.sh` and the Windows launchers. |
| `mlee_menu.py` | Console menu for staff testing (the Windows start-menu entry). |
| `reference/results.json` | Numbers from the macOS submission run. `build.py --compare` checks a new run against the reference for its platform. |
| `reference/results-windows.json` | The same numbers from the Windows x64 build (see *Cross-platform results*). |
| `windows/` | Windows installer: NSIS script, staging script, launchers, DLL check, staff guide. |

## Rebuild

```bash
./build.sh
```

The build needs Python 3 and [Tectonic](https://tectonic-typesetting.github.io). On first run it creates `.venv` from `requirements.txt`.

## Put your name on it

1. Edit the two lines in `report/meta.tex`.
2. Recompile without re-running the analysis:

```bash
./build.sh --pdf
```

## Notes

- **Seeds:** seed 42 is used throughout, so a rebuild reproduces `results.json` exactly.
- **Data downloads:** the CSVs are fetched with `curl` because this Python build has no CA certificates. Python reads only the local copies, after checking their SHA-256.
- **Analysis libraries:** only the permitted ones (scikit-learn, NumPy, SciPy, Matplotlib, seaborn). pandas is used only internally by seaborn. Pygments and PyMuPDF are used for building and checking the PDF, not for the analysis.

## Windows installer

GitHub Actions builds `MLEE_Assessment_Setup.exe` on every push to `main`. The workflow is `.github/workflows/windows-installer.yml`, running on `windows-2025`. It then installs the setup file, runs every launcher (with the TeX engine offline), compares the numbers with `reference/results.json`, and uninstalls it again.

The installer is per user and needs no admin rights or internet connection. It bundles:

- an embeddable CPython 3.13 with all the libraries
- an app-local copy of the Microsoft C++ runtime
- Tectonic, with a pre-filled TeX cache
- this project

To download the latest build:

```bash
gh run download --name MLEE_Assessment_Setup
```

To rebuild it on any Windows 10/11 PC that has Python 3.13:

```bash
powershell -ExecutionPolicy Bypass -File windows\build_windows.ps1
```

How to install and use the toolkit on Windows is covered in `windows/Staff Guide.html`.

## Cross-platform results

The Windows x64 build reproduces the macOS submission run to within 1e-6, except for 8 of the 199 recorded values. All 8 come from Task 1's *unconstrained*-tree experiments: the naive CV accuracy at depth 20, and the 100 repeated splits.

A fully grown tree reaches nodes where several candidate splits are exactly tied. Apple-silicon and x64 builds of scikit-learn round those sums differently, so the ties break differently. The depth-3 tree, Table 1 and Tasks 2-4 are unaffected.

Only one printed number changes: in Table 2, "Tuned better in 4 / 100 splits" (all test wines) becomes 3 / 100 on Windows. Results are deterministic within each platform, which is why the Windows reference is kept separately.
