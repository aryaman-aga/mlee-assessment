#!/usr/bin/env bash
# macOS/Linux wrapper around build.py (the cross-platform build).
#   ./build.sh            full build: analysis, PDF, checks
#   ./build.sh --pdf      recompile the PDF only (e.g. after editing meta.tex)
# The submission copy is written to ../MLEE_Assessment_Report.pdf.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

if [[ ! -x $PY ]]; then
  python3 -m venv .venv
  $PY -m pip install -q -r requirements.txt
fi

# Data: fetched with curl (the python.org macOS build has no CA bundle).
mkdir -p data
[[ -f data/winequality-red.csv ]] || curl -fsSL -o data/winequality-red.csv \
  https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-red.csv
[[ -f data/geyser.csv ]] || curl -fsSL -o data/geyser.csv \
  https://raw.githubusercontent.com/mwaskom/seaborn-data/master/geyser.csv

# Fonts for matplotlib, taken from the same TeX bundle the PDF uses.
mkdir -p fonts
for f in Regular Italic Bold BoldItalic Semibold Medium; do
  [[ -s fonts/Lato-$f.ttf ]] || tectonic -X bundle cat "Lato-$f.ttf" > "fonts/Lato-$f.ttf"
done

args=(--out ../MLEE_Assessment_Report.pdf)
[[ ${1:-} == --pdf ]] && args+=(--pdf-only)
exec $PY build.py "${args[@]}"
