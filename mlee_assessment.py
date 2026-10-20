#!/usr/bin/env python3
"""MLEE Course Assessment - reproducible analysis for all four tasks.

Running ``python mlee_assessment.py`` recomputes every number, table,
figure and code excerpt used in the PDF report:

    report/figures/*.pdf     vector figures (Lato, TrueType-embedded)
    report/generated/*.tex   result macros, tables, highlighted snippets
    results.json             every reported number, machine-readable

Code between ``# [snippet:taskN]`` and ``# [/snippet]`` markers is copied
verbatim, with its real line numbers, into the report.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # renders text extents; figures are saved as PDF
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import scipy  # noqa: E402
import seaborn as sns  # noqa: E402
import sklearn  # noqa: E402
from matplotlib import font_manager, patheffects  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb  # noqa: E402
from pygments import highlight  # noqa: E402
from pygments.formatters import LatexFormatter  # noqa: E402
from pygments.lexers import PythonLexer  # noqa: E402
from pygments.style import Style  # noqa: E402
from pygments.token import (Comment, Keyword, Name, Number,  # noqa: E402
                            Operator, String)
from scipy import stats  # noqa: E402
from scipy.optimize import linear_sum_assignment  # noqa: E402
from sklearn.datasets import load_breast_cancer  # noqa: E402
from sklearn.decomposition import PCA, FastICA  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (accuracy_score, f1_score,  # noqa: E402
                             precision_score, recall_score)
from sklearn.mixture import GaussianMixture  # noqa: E402
from sklearn.model_selection import (StratifiedGroupKFold,  # noqa: E402
                                     StratifiedKFold, cross_val_score,
                                     train_test_split, validation_curve)
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.tree import DecisionTreeClassifier, plot_tree  # noqa: E402

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FIGS = ROOT / "report" / "figures"
GEN = ROOT / "report" / "generated"
SEED = 42
SNIPPET_WIDTH = 56          # characters that fit a half-width code box
FULL_W, HALF_W = 7.0, 3.42  # inches: text width and one column of two

# Validated categorical pair (dataviz reference palette) + neutral inks.
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, NEUTRAL = "#e1e0d9", "#c3c2b7", "#f0efec"
BLUE, ORANGE, AQUA, BLUE_DARK = "#2a78d6", "#eb6834", "#1baf7a", "#1c5cab"
GAMMA_CMAP = LinearSegmentedColormap.from_list(
    "gamma", [BLUE, "#d9d8d2", ORANGE])  # diverging, grey at 0.5

RESULTS: dict[str, object] = {}  # raw values  -> results.json
TEX: dict[str, str] = {}         # formatted    -> \R{key} in LaTeX


# --------------------------------------------------------------------------
# Helpers: results, formatting, figures
# --------------------------------------------------------------------------
def note(key: str, value, text: str | None = None) -> None:
    """Record a raw result and the exact string the report prints."""
    if isinstance(value, np.generic):
        value = value.item()
    RESULTS[key] = value
    TEX[key] = str(value) if text is None else text


def f(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}"


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}"


def sig(x: float, n: int = 4) -> str:
    """n significant digits, keeping trailing zeros (33.70, 0.06916)."""
    return np.format_float_positional(x, precision=n, unique=False,
                                      fractional=False, trim="k")


def pmatrix(rows) -> str:
    body = r" \\ ".join(" & ".join(r) for r in rows)
    return r"\begin{pmatrix}" + body + r"\end{pmatrix}"


def setup_style() -> None:
    for ttf in sorted((ROOT / "fonts").glob("Lato-*.ttf")):
        font_manager.fontManager.addfont(str(ttf))
    for weight, expected in [("normal", "Lato-Regular.ttf"),
                             ("bold", "Lato-Bold.ttf")]:
        found = font_manager.findfont(
            font_manager.FontProperties(family="Lato", weight=weight),
            fallback_to_default=False)
        assert Path(found).name == expected, (weight, found)
    plt.rcParams.update({
        "font.family": "Lato", "font.size": 7.5,
        "pdf.fonttype": 42, "pdf.compression": 9,
        "text.color": INK, "axes.labelcolor": INK2,
        "axes.titlesize": 7.8, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.titlepad": 3.5,
        "axes.labelsize": 7.3, "xtick.labelsize": 6.8,
        "ytick.labelsize": 6.8, "legend.fontsize": 6.6,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.6,
        "xtick.color": INK2, "ytick.color": INK2,
        "xtick.major.size": 2.4, "ytick.major.size": 2.4,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
        "grid.linestyle": "-", "axes.axisbelow": True,
        "lines.linewidth": 1.4, "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "legend.frameon": False, "legend.handlelength": 1.5,
        "legend.borderaxespad": 0.2, "legend.labelspacing": 0.3,
        "figure.facecolor": "white", "savefig.facecolor": "white",
        "figure.constrained_layout.use": True,
        "figure.constrained_layout.h_pad": 0.015,
        "figure.constrained_layout.w_pad": 0.015,
        "axes.unicode_minus": True,
    })


def save(fig, name: str) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / f"{name}.pdf",
                metadata={"Creator": None, "Producer": None,
                          "CreationDate": None})
    plt.close(fig)


def tint(color: str, amount: float) -> tuple:
    """Mix `color` with white; amount=1 -> color, 0 -> white."""
    c = np.array(to_rgb(color))
    return tuple(1 - amount * (1 - c))


# --------------------------------------------------------------------------
# Task 1 - Decision trees on UCI red wine quality
# --------------------------------------------------------------------------
WINE_FEATURES = ["fixed acidity", "volatile acidity", "citric acid",
                 "residual sugar", "chlorides", "free SO\u2082",
                 "total SO\u2082", "density", "pH", "sulphates", "alcohol"]


def make_trees() -> dict:
    return {
        "default": DecisionTreeClassifier(random_state=SEED),
        "tuned": DecisionTreeClassifier(
            max_depth=3, min_samples_leaf=5, random_state=SEED),
    }


def unseen_mask(X_tr, X_te):
    """True for test rows with no exact duplicate in the training set."""
    seen = {row.tobytes() for row in X_tr}
    return np.array([row.tobytes() not in seen for row in X_te])


def verify_data() -> None:
    """Fail fast if a dataset differs from the recorded SHA-256."""
    for line in (DATA / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split()
        actual = hashlib.sha256((DATA / name).read_bytes()).hexdigest()
        assert actual == digest, f"{name}: checksum mismatch"


def task1() -> None:
    # [snippet:task1]
    raw = np.genfromtxt(DATA / "winequality-red.csv",
                        delimiter=";", skip_header=1)
    X, y = raw[:, :-1], (raw[:, -1] >= 6).astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=SEED)

    default = DecisionTreeClassifier(random_state=SEED)
    tuned = DecisionTreeClassifier(max_depth=3,
                                   min_samples_leaf=5,
                                   random_state=SEED)
    trees = {"default": default, "tuned": tuned}
    metrics = (accuracy_score, precision_score,
               recall_score)
    table = {}
    for name, tree in trees.items():
        y_hat = tree.fit(X_tr, y_tr).predict(X_te)
        table[name] = [m(y_te, y_hat) for m in metrics]

    # 240 wines are exact duplicates: keep twins in one fold
    _, groups = np.unique(X_tr, axis=0, return_inverse=True)
    cv = StratifiedGroupKFold(10, shuffle=True,
                              random_state=SEED)
    depths = np.arange(1, 21)
    train_sc, cv_sc = validation_curve(
        DecisionTreeClassifier(random_state=SEED),
        X_tr, y_tr, groups=groups, cv=cv,
        param_name="max_depth", param_range=depths)
    # [/snippet]

    # ---- data facts -------------------------------------------------------
    n_dup = len(X) - len(np.unique(X, axis=0))
    n_dup_rows = len(raw) - len(np.unique(raw, axis=0))
    assert X.shape == (1599, 11) and n_dup == 240 == n_dup_rows
    assert (y == 1).sum() == 855 and (y == 0).sum() == 744
    note("t1-n", len(X), f"{len(X):,}")
    note("t1-nhigh", int(y.sum()))
    note("t1-nlow", int((1 - y).sum()))
    note("t1-phigh", float(y.mean()), pct(y.mean()))
    note("t1-ntrain", len(X_tr), f"{len(X_tr):,}")
    note("t1-ntest", len(X_te))
    note("t1-dups", n_dup)
    note("t1-unique", len(X) - n_dup, f"{len(X) - n_dup:,}")

    unseen = unseen_mask(X_tr, X_te)
    note("t1-twin-n", int((~unseen).sum()))
    note("t1-unseen-n", int(unseen.sum()))
    note("t1-twin-pct", float((~unseen).mean()), pct((~unseen).mean(), 0))

    # ---- Table 1: held-out metrics + diagnostics ---------------------------
    rows = {}
    for name, tree in trees.items():
        y_hat = tree.predict(X_te)
        r = {
            "acc": accuracy_score(y_te, y_hat),
            "prec": precision_score(y_te, y_hat),
            "rec": recall_score(y_te, y_hat),
            "f1": f1_score(y_te, y_hat),
            "train": accuracy_score(y_tr, tree.predict(X_tr)),
            "unseen": accuracy_score(y_te[unseen], y_hat[unseen]),
            "twin": accuracy_score(y_te[~unseen], y_hat[~unseen]),
            "depth": tree.get_depth(),
            "leaves": tree.get_n_leaves(),
        }
        r["gap"] = r["train"] - r["acc"]
        assert [r["acc"], r["prec"], r["rec"]] == table[name]
        rows[name] = r
        for k, v in r.items():
            text = str(v) if k in ("depth", "leaves") else f(v)
            if k == "gap":
                text = f"{100 * v:.1f}"
            note(f"t1-{name}-{k}", v, text)
    write_table1(rows)

    # ---- validation curves: duplicate-aware vs naive CV --------------------
    _, naive_cv = validation_curve(
        DecisionTreeClassifier(random_state=SEED), X_tr, y_tr,
        param_name="max_depth", param_range=depths,
        cv=StratifiedKFold(10, shuffle=True, random_state=SEED))
    g_mean, g_sd = cv_sc.mean(1), cv_sc.std(1)
    best = int(depths[np.argmax(g_mean)])
    note("t1-cv-best-depth", best)
    note("t1-cv-best", float(g_mean.max()), f(g_mean.max()))
    note("t1-cv-d3", float(g_mean[2]), f(g_mean[2]))
    note("t1-cv-d20", float(g_mean[-1]), f(g_mean[-1]))
    note("t1-naive-d20", float(naive_cv.mean(1)[-1]),
         f(naive_cv.mean(1)[-1]))
    note("t1-train-d20", float(train_sc.mean(1)[-1]),
         f(train_sc.mean(1)[-1]))
    plot_validation(depths, train_sc, cv_sc, naive_cv, best)

    # ---- repeated splits: where does the default tree's edge come from? --
    reps = {m: {"all": [], "unseen": []} for m in trees}
    n_rep = 100
    for s in range(n_rep):
        a_tr, a_te, b_tr, b_te = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=1000 + s)
        mask = unseen_mask(a_tr, a_te)
        for name, tree in make_trees().items():
            pred = tree.fit(a_tr, b_tr).predict(a_te)
            reps[name]["all"].append(accuracy_score(b_te, pred))
            reps[name]["unseen"].append(
                accuracy_score(b_te[mask], pred[mask]))
    note("t1-reps", n_rep)
    for name in trees:
        for part in ("all", "unseen"):
            v = np.array(reps[name][part])
            note(f"t1-rep-{name}-{part}", float(v.mean()), f(v.mean()))
            note(f"t1-rep-{name}-{part}-sd", float(v.std()), f(v.std()))
    for part in ("all", "unseen"):
        d = np.array(reps["tuned"][part]) - np.array(reps["default"][part])
        note(f"t1-rep-tunedwins-{part}", int((d > 0).sum()))
        note(f"t1-rep-diff-{part}", float(d.mean()), f"{100 * d.mean():+.1f}")

    plot_tree_figure(trees["tuned"])


def write_table1(rows: dict) -> None:
    cols = [("acc", max), ("prec", max), ("rec", max), ("f1", max),
            ("train", None), ("gap", min), ("depth", None),
            ("leaves", None), ("unseen", max)]
    names = {"default": r"(a) Default, unconstrained",
             "tuned": r"(b) Tuned, depth 3 / leaf 5"}
    lines = []
    for name, r in rows.items():
        cells = [names[name]]
        for key, better in cols:
            v = r[key]
            if key in ("depth", "leaves"):
                text = str(v)
            elif key == "gap":
                text = f"{100 * v:.1f}"
            else:
                text = f(v)
            if better and v == better(rows[m][key] for m in rows) \
                    and len({rows[m][key] for m in rows}) > 1:
                text = rf"\textbf{{{text}}}"
            cells.append(text)
        lines.append(" & ".join(cells) + r" \\")
    (GEN / "table1_rows.tex").write_text(
        "\\def\\tableonerows{%\n" + "\n".join(lines) + "}\n",
        encoding="utf-8", newline="\n")


def plot_validation(depths, train_sc, cv_sc, naive_cv, best) -> None:
    fig, ax = plt.subplots(figsize=(HALF_W, 2.28))
    tr, g, nv = train_sc.mean(1), cv_sc.mean(1), naive_cv.mean(1)
    ax.fill_between(depths, g - cv_sc.std(1), g + cv_sc.std(1),
                    color=BLUE, alpha=0.12, lw=0)
    ax.plot(depths, tr, color=INK2, lw=1.2, label="Training accuracy")
    ax.plot(depths, nv, color=ORANGE, lw=1.1, ls=(0, (4, 2)),
            label="Naive CV (twins leak)")
    ax.plot(depths, g, color=BLUE, lw=1.6, marker="o", ms=3.2,
            mec="white", mew=0.6, label="Duplicate-aware CV \u00b11 sd")
    ax.axvline(3, color=MUTED, lw=0.8)
    ax.text(3.25, 0.985, "tuned tree\n(depth 3)", color=INK2, fontsize=6.4,
            va="top", ha="left")
    i = int(np.argmax(g))
    ax.plot(best, g[i], marker="o", ms=6.5, mfc="none", mec=INK, mew=1.0,
            zorder=5)
    ax.annotate(f"CV peak {g[i]:.3f} at depth {best}", (best, g[i]),
                xytext=(5.6, 0.768), fontsize=6.4, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    ax.set_xlim(0.5, 20.5)
    ax.set_ylim(0.6, 1.005)
    ax.set_xticks([1, 3, 5, 10, 15, 20])
    ax.set_xlabel("max_depth")
    ax.set_ylabel("Accuracy")
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.555),
              fontsize=6.3)
    save(fig, "t1_validation")


def plot_tree_figure(tree) -> None:
    fig, ax = plt.subplots(figsize=(FULL_W, 2.62))
    anns = plot_tree(tree, feature_names=WINE_FEATURES,
                     class_names=["low", "high"], filled=True,
                     rounded=True, impurity=True, fontsize=6, ax=ax)
    t = tree.tree_
    nodes = [a for a in anns if a.get_bbox_patch() is not None]
    edge_labels = [a for a in anns if a.get_bbox_patch() is None]
    assert len(nodes) == t.node_count and len(edge_labels) == 2
    for i, ann in enumerate(nodes):
        n = int(t.n_node_samples[i])
        assert f"samples = {n}" in ann.get_text(), (i, ann.get_text())
        v = t.value[i, 0]
        p_high = v[1] / v.sum()
        leaf = t.children_left[i] == -1
        if leaf:
            head = f"leaf \u2192 {'HIGH' if p_high >= 0.5 else 'LOW'}"
        else:
            name = WINE_FEATURES[t.feature[i]]
            head = f"{name} \u2264 {t.threshold[i]:.4g}"
        ann.set_text(f"{head}\nn = {n}  \u00b7  {100 * p_high:.0f}% high"
                     f"\nGini {t.impurity[i]:.3f}")
        base = ORANGE if p_high >= 0.5 else BLUE
        purity = abs(2 * p_high - 1)
        box = ann.get_bbox_patch()
        box.set_facecolor(tint(base, 0.10 + 0.50 * purity))
        box.set_edgecolor(tint(base, 0.9))
        box.set_linewidth(0.7)
        ann.set_color(INK)
        ann.set_fontsize(6.5)
        if ann.arrow_patch is not None:
            ann.arrow_patch.set_color(MUTED)
            ann.arrow_patch.set_linewidth(0.7)
    for lab in edge_labels:
        lab.set_text({"True": "yes (≤)  ", "False": "  no (>)"}
                     [lab.get_text().strip()])
        lab.set_color(INK2)
        lab.set_fontsize(6.4)
    note("t1-tree-nodes", int(t.node_count))
    note("t1-root-feature", WINE_FEATURES[t.feature[0]])
    note("t1-root-threshold", float(t.threshold[0]),
         f"{t.threshold[0]:.4g}")
    imp = tree.feature_importances_
    order = np.argsort(imp)[::-1]
    top = [(WINE_FEATURES[j], float(imp[j])) for j in order[:3]]
    note("t1-top-features", top,
         ", ".join(f"{nm} ({100 * w:.0f}\\,\\%)" for nm, w in top)
         .replace("\u2082", r"\textsubscript{2}"))
    save(fig, "t1_tree")


# --------------------------------------------------------------------------
# Task 2 - Gaussian mixture on Old Faithful via EM
# --------------------------------------------------------------------------
def task2() -> None:
    # [snippet:task2]
    geyser = sns.load_dataset("geyser", data_home=DATA)
    X = geyser[["duration", "waiting"]].to_numpy(float)
    gmm = GaussianMixture(
        n_components=2, covariance_type="full",
        n_init=10, tol=1e-6, random_state=SEED).fit(X)
    k = np.argsort(gmm.means_[:, 0])     # short, long
    pi, mu = gmm.weights_[k], gmm.means_[k]
    Sigma = gmm.covariances_[k]
    gamma = gmm.predict_proba(X)[:, k]   # soft assignments
    # [/snippet]

    assert X.shape == (272, 2) and gmm.converged_
    n = len(X)
    note("t2-n", n)
    note("t2-niter", int(gmm.n_iter_))
    note("t2-loglik", float(gmm.score(X) * n), f"{gmm.score(X) * n:.2f}")
    note("t2-bic", float(gmm.bic(X)), f"{gmm.bic(X):.1f}")
    for j in range(2):
        tag = j + 1
        note(f"t2-pi{tag}", float(pi[j]), f(pi[j]))
        note(f"t2-mu{tag}", mu[j].tolist(),
             pmatrix([[sig(mu[j][0])], [sig(mu[j][1])]]))
        S = Sigma[j]
        note(f"t2-S{tag}", S.tolist(),
             pmatrix([[sig(S[0, 0]), sig(S[0, 1])],
                      [sig(S[1, 0]), sig(S[1, 1])]]))
        rho = S[0, 1] / np.sqrt(S[0, 0] * S[1, 1])
        note(f"t2-rho{tag}", float(rho), f(rho, 2))
        note(f"t2-mu{tag}-dur", float(mu[j][0]), f(mu[j][0], 2))
        note(f"t2-mu{tag}-wait", float(mu[j][1]), f(mu[j][1], 1))
        note(f"t2-sd{tag}-dur", float(np.sqrt(S[0, 0])),
             f(np.sqrt(S[0, 0]), 2))
        note(f"t2-sd{tag}-wait", float(np.sqrt(S[1, 1])),
             f(np.sqrt(S[1, 1]), 1))
    g_long = gamma[:, 1]
    ambiguous = (g_long > 0.1) & (g_long < 0.9)
    assert ambiguous.sum() == 1, "caption: exactly one ambiguous point"
    note("t2-ambiguous", int(ambiguous.sum()))
    note("t2-hard-long", int((g_long >= 0.5).sum()))
    # sanity: sklearn's ellipse-free check that the means are well separated
    assert mu[0][0] < 3 < mu[1][0]

    # EM convergence from a deliberately poor (random) start
    em = GaussianMixture(2, covariance_type="full", init_params="random",
                         tol=1e-6, max_iter=500,
                         random_state=SEED).fit(X)
    trace = np.asarray(em.lower_bounds_)
    assert np.all(np.diff(trace) >= -1e-9), "EM must be monotone"
    assert abs(em.score(X) - gmm.score(X)) < 1e-6, "same optimum"
    note("t2-em-iters", int(em.n_iter_))
    note("t2-em-start", float(trace[0] * n), f"{trace[0] * n:.1f}")

    bics = {}
    for kk in range(1, 5):
        m = GaussianMixture(kk, covariance_type="full", n_init=10,
                            tol=1e-6, random_state=SEED).fit(X)
        bics[kk] = float(m.bic(X))
    note("t2-bics", bics,
         ", ".join(f"$K{{=}}{kk}$: {b:.1f}" for kk, b in bics.items()))
    note("t2-bic-best", int(min(bics, key=bics.get)))

    plot_gmm(X, gmm, k, pi, mu, Sigma, g_long, ambiguous)
    plot_em(trace * n, gmm.score(X) * n)


# [snippet:task2]
def ellipse(m, S, mass, n=200):
    """Contour of N(m, S) holding `mass` probability."""
    r = np.sqrt(stats.chi2.ppf(mass, df=2))  # radius
    vals, vecs = np.linalg.eigh(S)    # principal axes
    t = np.linspace(0, 2 * np.pi, n)
    unit = np.stack([np.cos(t), np.sin(t)])
    return m + r * ((vecs * np.sqrt(vals)) @ unit).T
# [/snippet]


def plot_gmm(X, gmm, k, pi, mu, Sigma, g_long, ambiguous) -> None:
    fig, ax = plt.subplots(figsize=(HALF_W, 2.62))
    x0, x1, y0, y1 = 1.3, 5.45, 38, 101
    gx, gy = np.meshgrid(np.linspace(x0, x1, 400), np.linspace(y0, y1, 400))
    field = gmm.predict_proba(np.c_[gx.ravel(), gy.ravel()])[:, k[1]]
    field = field.reshape(gx.shape)
    ax.imshow(field, extent=(x0, x1, y0, y1), origin="lower",
              cmap=GAMMA_CMAP, vmin=0, vmax=1, alpha=0.16,
              aspect="auto", interpolation="bilinear", zorder=0)
    cs = ax.contour(gx, gy, field, levels=[0.5], colors=[INK2],
                    linewidths=0.7, zorder=1)
    ax.clabel(cs, fmt={0.5: "\u03b3 = 0.5"}, fontsize=6, inline=True,
              inline_spacing=2, manual=[(2.95, 92)])
    for j, col in enumerate([BLUE, ORANGE]):
        for mass, lw, a in [(0.5, 1.1, 1.0), (0.9, 0.8, 0.8),
                            (0.99, 0.6, 0.6)]:
            e = ellipse(mu[j], Sigma[j], mass)
            ax.plot(e[:, 0], e[:, 1], color=col, lw=lw, alpha=a, zorder=2)
    sc = ax.scatter(X[:, 0], X[:, 1], c=g_long, cmap=GAMMA_CMAP, vmin=0,
                    vmax=1, s=11, lw=0.45, edgecolors="white", zorder=3)
    ax.scatter(X[ambiguous, 0], X[ambiguous, 1], s=26, facecolors="none",
               edgecolors=INK, lw=0.8, zorder=4)
    halo = [patheffects.withStroke(linewidth=2.2, foreground="white")]
    for j in range(2):
        ax.plot(*mu[j], marker="+", color=INK, ms=7, mew=1.3, zorder=5)
        ax.text(mu[j][0] + 0.07, mu[j][1] + 1.3,
                f"\u03bc{'\u2081\u2082'[j]}", fontsize=7.2, color=INK,
                fontweight="bold", zorder=6, path_effects=halo)
    ax.text(0.985, 0.018, "ellipses: 50 / 90 / 99 % probability mass\n"
            "\u25cb  only point with 0.1 < \u03b3 < 0.9",
            transform=ax.transAxes, fontsize=6.0, color=INK2, va="bottom",
            ha="right", linespacing=1.25)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_xlabel("Eruption duration (min)")
    ax.set_ylabel("Waiting time to next eruption (min)")
    cb = fig.colorbar(sc, ax=ax, pad=0.015, fraction=0.06, aspect=28)
    cb.set_label("\u03b3(long) = P(long component | x)", fontsize=6.6,
                 color=INK2)
    cb.ax.tick_params(labelsize=6.2, length=2)
    cb.outline.set_linewidth(0.4)
    cb.outline.set_edgecolor(AXIS)
    save(fig, "t2_gmm")


def plot_em(loglik, final) -> None:
    fig, ax = plt.subplots(figsize=(2.2, 1.36))
    it = np.arange(1, len(loglik) + 1)
    ax.plot(it, loglik, color=BLUE, lw=1.4, marker="o", ms=2.6,
            mec="white", mew=0.5)
    ax.axhline(final, color=MUTED, lw=0.7)
    label = f"converged: log L = {final:.2f}".replace("-", "\u2212")
    ax.text(1, final - 0.045 * (final - loglik[0]), label, ha="left",
            va="top", fontsize=6.3, color=INK2)
    ax.set_xlabel("EM iteration (random start)", labelpad=1)
    ax.set_ylabel("Log-likelihood", labelpad=1)
    save(fig, "t2_em")


# --------------------------------------------------------------------------
# Task 3 - PCA on Breast Cancer Wisconsin (Diagnostic)
# --------------------------------------------------------------------------
def task3() -> None:
    # [snippet:task3]
    data = load_breast_cancer()             # 569 x 30
    Z = StandardScaler().fit_transform(data.data)
    pca = PCA().fit(Z)                      # all 30 PCs
    cum = np.cumsum(pca.explained_variance_ratio_)
    k85 = int(np.argmax(cum >= 0.85)) + 1   # first k >= .85
    assert k85 == PCA(0.85).fit(Z).n_components_
    scores = pca.transform(Z)[:, :2]        # PC1, PC2
    malignant = data.target == 0            # 0 = malignant
    # [/snippet]

    assert Z.shape == (569, 30) and malignant.sum() == 212
    evr = pca.explained_variance_ratio_
    note("t3-n", len(Z))
    note("t3-nmal", int(malignant.sum()))
    note("t3-nben", int((~malignant).sum()))
    note("t3-evr1", float(evr[0]), pct(evr[0]))
    note("t3-evr2", float(evr[1]), pct(evr[1]))
    note("t3-evr12", float(evr[:2].sum()), pct(evr[:2].sum()))
    note("t3-k85", k85)
    note("t3-cum-k85", float(cum[k85 - 1]), pct(cum[k85 - 1]))
    note("t3-cum-km1", float(cum[k85 - 2]), pct(cum[k85 - 2]))
    for thr in (90, 95, 99):
        note(f"t3-k{thr}", int(np.argmax(cum >= thr / 100)) + 1)
    note("t3-cum", cum.tolist(), ", ".join(pct(c) for c in cum[:7]))

    raw_pca = PCA().fit(data.data)
    j = int(np.argmax(np.abs(raw_pca.components_[0])))
    note("t3-raw-evr1", float(raw_pca.explained_variance_ratio_[0]),
         pct(raw_pca.explained_variance_ratio_[0]))
    note("t3-raw-top", str(data.feature_names[j]))

    clf = make_pipeline(StandardScaler(), PCA(2), LogisticRegression())
    acc = cross_val_score(clf, data.data, data.target,
                          cv=StratifiedKFold(10, shuffle=True,
                                             random_state=SEED))
    note("t3-lr-acc", float(acc.mean()), pct(acc.mean()))
    note("t3-lr-sd", float(acc.std()), pct(acc.std()))

    load = pca.components_[:2].T * np.sqrt(pca.explained_variance_[:2])
    top1 = np.argsort(-np.abs(load[:, 0]))[:3]
    top2 = np.argsort(-np.abs(load[:, 1]))[:2]
    note("t3-pc1-top", [str(data.feature_names[i]) for i in top1],
         ", ".join(f"\\emph{{{data.feature_names[i]}}}" for i in top1))
    note("t3-pc2-top", [str(data.feature_names[i]) for i in top2],
         ", ".join(f"\\emph{{{data.feature_names[i]}}}" for i in top2))
    assert (pca.components_[0] > 0).all(), "text: all PC1 loadings > 0"
    note("t3-pc1-pos", int((pca.components_[0] > 0).sum()))
    mal_side = np.sign(scores[malignant, 0].mean())
    note("t3-mal-side", "positive" if mal_side > 0 else "negative")

    # biplot arrows: strongest loadings, at least 28 degrees apart
    arrows, angles = [], []
    for i in np.argsort(-np.linalg.norm(load, axis=1)):
        a = np.degrees(np.arctan2(load[i, 1], load[i, 0]))
        if all(abs((a - b + 180) % 360 - 180) >= 28 for b in angles):
            arrows.append(i)
            angles.append(a)
        if len(arrows) == 4:
            break
    note("t3-arrows", [str(data.feature_names[i]) for i in arrows])

    plot_variance(evr, cum, k85)
    plot_pc_scatter(scores, malignant, evr, load, data.feature_names,
                    arrows)


def plot_variance(evr, cum, k85) -> None:
    fig, ax = plt.subplots(figsize=(HALF_W, 2.28))
    k = np.arange(1, len(evr) + 1)
    ax.bar(k, 100 * evr, width=0.62, color=tint(BLUE, 0.38), lw=0,
           label="Individual PC")
    ax.plot(k, 100 * cum, color=BLUE_DARK, lw=1.5, marker="o", ms=3,
            mec="white", mew=0.6, label="Cumulative ratio", zorder=3)
    ax.axhline(85, color=ORANGE, lw=0.9, zorder=2)
    ax.text(30.4, 85 - 2.0, "85 % threshold", ha="right", va="top",
            fontsize=6.4, color=INK2)
    ax.plot([k85, k85], [0, 100 * cum[k85 - 1]], color=INK2, lw=0.7)
    ax.plot(k85, 100 * cum[k85 - 1], marker="o", ms=6.5, mfc="none",
            mec=INK, mew=1.1, zorder=4)
    ax.annotate(f"k = {k85} PCs \u2192 {100 * cum[k85 - 1]:.1f} %\n"
                f"(k = {k85 - 1} gives only {100 * cum[k85 - 2]:.1f} %)",
                (k85, 100 * cum[k85 - 1]), xytext=(9.0, 55),
                fontsize=6.5, color=INK, arrowprops=dict(
                    arrowstyle="-", color=INK2, lw=0.6))
    marks = []
    for thr in (90, 95, 99):
        kk = int(np.argmax(cum >= thr / 100)) + 1
        ax.plot(kk, 100 * cum[kk - 1], marker="o", ms=5, mfc="none",
                mec=INK2, mew=0.8, zorder=4)
        marks.append(f"{thr} % → k = {kk}")
    ax.text(30.4, 106.5, "   ·   ".join(marks), ha="right",
            va="center", fontsize=6.2, color=INK2)
    ax.set_xlim(0.3, 30.7)
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_xticks([1, 5, 10, 15, 20, 25, 30])
    ax.set_xlabel("Number of principal components")
    ax.set_ylabel("Explained variance ratio (%)")
    ax.set_title("Cumulative explained variance ratio vs. number of PCs")
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.42))
    save(fig, "t3_variance")


def plot_pc_scatter(scores, malignant, evr, load, names, arrows) -> None:
    fig, ax = plt.subplots(figsize=(HALF_W, 2.62))
    groups = [(~malignant, "Benign", BLUE, "o", 9),
              (malignant, "Malignant", ORANGE, "^", 11)]
    for mask, label, col, mk, size in groups:
        pts = scores[mask]
        ax.scatter(pts[:, 0], pts[:, 1], s=size, marker=mk, color=col,
                   alpha=0.85, lw=0.35, edgecolors="white",
                   label=f"{label} (n = {mask.sum()})", zorder=2)
        e = ellipse(pts.mean(0), np.cov(pts.T), 0.95)
        ax.plot(e[:, 0], e[:, 1], color=col, lw=0.9, zorder=3)
    scale = 7.0
    halo = [patheffects.withStroke(linewidth=2.0, foreground="white")]
    for i in arrows:
        vx, vy = scale * load[i]
        ax.annotate("", (vx, vy), (0, 0), zorder=4,
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.8,
                                    mutation_scale=6))
        ux, uy = np.array([vx, vy]) / np.hypot(vx, vy)
        ax.text(vx + 0.45 * ux, vy + 0.45 * uy, names[i], fontsize=5.9,
                color=INK, ha="left" if ux >= 0 else "right",
                va="bottom" if uy >= 0 else "top", zorder=5,
                path_effects=halo)
    ax.axhline(0, color=AXIS, lw=0.5, zorder=1)
    ax.axvline(0, color=AXIS, lw=0.5, zorder=1)
    ax.set_xlabel(f"PC1 ({100 * evr[0]:.1f} % of variance)")
    ax.set_ylabel(f"PC2 ({100 * evr[1]:.1f} % of variance)")
    ax.legend(loc="upper right", markerscale=1.4, handletextpad=0.3)
    save(fig, "t3_scatter")


# --------------------------------------------------------------------------
# Task 4 - Blind source separation with FastICA (vs PCA)
# --------------------------------------------------------------------------
def amari(P) -> float:
    """Amari index: 0 when P is a scaled permutation matrix."""
    P = np.abs(P)
    n = len(P)
    rows = (P / P.max(1, keepdims=True)).sum(1) - 1
    cols = (P / P.max(0, keepdims=True)).sum(0) - 1
    return float((rows.sum() + cols.sum()) / (2 * n * (n - 1)))


def task4() -> None:
    # [snippet:task4]
    t = np.linspace(0, 1, 1000)
    S = np.c_[np.sin(2 * np.pi * t * 5),     # sine
              np.sign(np.sin(2 * np.pi * t * 3))]  # square
    A = np.array([[1, 1], [0.5, 2.0]])       # mixing
    X = S @ A.T                              # mixtures

    ica = FastICA(n_components=2, whiten="unit-variance",
                  tol=1e-8, max_iter=2000,
                  random_state=SEED)
    S_ica = ica.fit_transform(X)             # unmixed
    pca = PCA(n_components=2).fit(X)
    S_pca = pca.transform(X)                 # decorrelated

    # sources are recovered only up to order, sign and scale
    S_ica, r_ica, _, _ = match(S, S_ica)
    S_pca, r_pca, leak_pca, _ = match(S, S_pca)
    # [/snippet]

    assert X.shape == (1000, 2)
    _, _, leak_ica, col_ica = match(S, ica.transform(X))
    assert r_ica.min() > 0.999 and r_pca.min() < 0.99
    for i, src in enumerate(["sine", "square"]):
        note(f"t4-r-ica-{src}", float(r_ica[i]), f(r_ica[i], 4))
        note(f"t4-r-pca-{src}", float(r_pca[i]), f(r_pca[i], 3))
        note(f"t4-leak-pca-{src}", float(leak_pca[i]), f(leak_pca[i], 2))
        note(f"t4-leak-ica-{src}", float(leak_ica[i]), f(leak_ica[i], 3))
    note("t4-r-ica-min", float(r_ica.min()), f(r_ica.min(), 4))
    note("t4-r-pca-min", float(r_pca.min()), f(r_pca.min(), 3))
    note("t4-leak-pca-max", float(leak_pca.max()), f(leak_pca.max(), 2))
    note("t4-amari-ica", amari(ica.components_ @ A),
         f(amari(ica.components_ @ A), 3))
    note("t4-amari-pca", amari(pca.components_ @ A),
         f(amari(pca.components_ @ A), 3))
    kurt = stats.kurtosis(S, axis=0)
    note("t4-kurt-sine", float(kurt[0]), f(kurt[0], 2))
    note("t4-kurt-square", float(kurt[1]), f(kurt[1], 2))

    def angle(v):
        return float(np.degrees(np.arctan2(v[1], v[0])) % 180)

    a1, a2 = angle(A[:, 0]), angle(A[:, 1])
    pc1 = angle(pca.components_[0])
    ica_dirs = [angle(ica.mixing_[:, c]) for c in col_ica]
    note("t4-angle-a1", a1, f(a1, 1))
    note("t4-angle-a2", a2, f(a2, 1))
    note("t4-angle-between", a2 - a1, f(a2 - a1, 1))
    note("t4-angle-pc1", pc1, f(pc1, 1))
    note("t4-angle-ica1", ica_dirs[0], f(ica_dirs[0], 1))
    note("t4-angle-ica2", ica_dirs[1], f(ica_dirs[1], 1))
    note("t4-pc1-var", float(pca.explained_variance_ratio_[0]),
         pct(pca.explained_variance_ratio_[0]))
    P = ica.components_ @ A
    note("t4-WA", P.tolist(), pmatrix([[f(v, 3) for v in r] for r in P]))

    plot_signals(t, S, X, S_ica, r_ica)
    plot_geometry(X, A, pca, ica, col_ica, t, S_pca, r_pca, leak_pca)


# [snippet:task4]
def match(S, S_hat):
    """Match estimates to sources (order/sign/scale)."""
    C = np.corrcoef(S.T, S_hat.T)[:2, 2:]  # true x est
    row, col = linear_sum_assignment(-np.abs(C))
    out = S_hat[:, col] * np.sign(C[row, col])
    out = (out - out.mean(0)) / out.std(0)
    out = out * S.std(0) + S.mean(0)
    r = np.abs(C[row, col])                # |corr|
    leak = np.abs(C[row, col[::-1]])       # cross-talk
    return out, r, leak, col
# [/snippet]


def _trace(ax, t, y, offset, color, label, lw=1.2, **kw):
    ax.plot(t, y + offset, color=color, lw=lw, **kw)
    if label:
        ax.text(1.008, offset, label, transform=ax.get_yaxis_transform(),
                fontsize=6.4, color=INK, va="center", ha="left")


def plot_signals(t, S, X, S_ica, r_ica) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(FULL_W, 3.3), sharex=True)
    rows = [
        ("(1) Original source signals  S", [
            (S[:, 0], 1.6, BLUE, "s\u2081  sine, 5 Hz"),
            (S[:, 1], -1.6, ORANGE, "s\u2082  square, 3 Hz")]),
        ("(2) Mixed signals  X = S A\u1d40  "
         "with  A = [[1, 1], [0.5, 2]]", [
             (X[:, 0], 2.6, INK2, "x\u2081 = s\u2081 + s\u2082"),
             (X[:, 1], -2.6, MUTED, "x\u2082 = 0.5 s\u2081 + 2 s\u2082")]),
        ("(3) Recovered signals via FastICA (order, sign and scale aligned;"
         "  grey underlay = true sources)", [
            (S_ica[:, 0], 1.6, BLUE, f"\u015d\u2081   |r| = {r_ica[0]:.4f}"),
            (S_ica[:, 1], -1.6, ORANGE,
             f"\u015d\u2082   |r| = {r_ica[1]:.4f}")]),
    ]
    for ax, (title, traces) in zip(axes, rows):
        if ax is axes[2]:
            for i, off in enumerate([1.6, -1.6]):
                ax.plot(t, S[:, i] + off, color="#cfcdc6", lw=4.2,
                        solid_capstyle="butt", zorder=1)
        for y, off, col, label in traces:
            _trace(ax, t, y, off, col, label, lw=1.1 if ax is axes[2]
                   else 1.2, zorder=2)
        ax.set_title(title, fontsize=7.2)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.grid(axis="y", visible=False)
    axes[0].set_ylim(-3.0, 3.0)
    axes[1].set_ylim(-5.6, 5.6)
    axes[2].set_ylim(-3.0, 3.0)
    axes[-1].set_xlim(0, 1)
    axes[-1].set_xlabel("Time t (s), 1000 samples")
    save(fig, "t4_signals")


def plot_geometry(X, A, pca, ica, col_ica, t, S_pca, r_pca, leak) -> None:
    fig = plt.figure(figsize=(HALF_W, 3.05))
    gs = fig.add_gridspec(2, 1, height_ratios=[2.15, 1.0])
    ax = fig.add_subplot(gs[0])
    Xc = X - X.mean(0)
    ax.scatter(Xc[:, 0], Xc[:, 1], s=2.2, color=MUTED, alpha=0.45, lw=0,
               zorder=1)
    L = 3.2

    def line(v, **kw):
        v = np.asarray(v, float) / np.linalg.norm(v)
        ax.plot([-L * v[0], L * v[0]], [-L * v[1], L * v[1]], **kw)

    halo = [patheffects.withStroke(linewidth=2.0, foreground="white")]
    for j, (col, name) in enumerate([(BLUE, "a\u2081 sine"),
                                     (ORANGE, "a\u2082 square")]):
        line(A[:, j], color=col, lw=2.8, alpha=0.32, zorder=2)
        line(ica.mixing_[:, col_ica[j]], color=col, lw=1.0, zorder=3)
        v = A[:, j] / np.linalg.norm(A[:, j])
        ax.text(*(-3.0 * v + [0.08, -0.05]), name, fontsize=6.3, color=INK,
                ha="left", va="top", zorder=6, path_effects=halo)
    for j, name in enumerate(["PC1", "PC2"]):
        v = pca.components_[j] / np.linalg.norm(pca.components_[j])
        line(v, color=INK, lw=0.9, ls=(0, (3, 1.6)), zorder=4)
        p = 2.55 * (v if v[1] > 0 else -v)
        ax.text(p[0] - 0.12, p[1], name, fontsize=6.3, color=INK,
                ha="right", va="center", zorder=6, path_effects=halo)
    ax.plot([], [], color=INK2, lw=2.8, alpha=0.32,
            label="true axis\n(column of A)")
    ax.plot([], [], color=INK2, lw=1.0, label="FastICA\nestimate")
    ax.plot([], [], color=INK, lw=0.9, ls=(0, (3, 1.6)),
            label="PCA axes\n(orthogonal)")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=6.2,
              handlelength=1.8, labelspacing=0.9)
    ax.set_xlim(-3.1, 3.1)
    ax.set_ylim(-3.4, 3.4)
    ax.set_aspect("equal")
    ax.set_xlabel("x\u2081 (centred)", labelpad=1)
    ax.set_ylabel("x\u2082 (centred)", labelpad=1)
    ax.set_title("Mixtures x\u2081 vs x\u2082", fontsize=7.2)

    ax2 = fig.add_subplot(gs[1])
    for i, (col, off) in enumerate([(INK2, 1.7), (MUTED, -1.7)]):
        y = S_pca[:, i]
        ax2.plot(t, (y - y.mean()) / y.std() + off, color=col, lw=0.9)
    ax2.set_title(f"PCA outputs stay mixed: |r| \u2264 {r_pca.max():.3f}, "
                  f"cross-talk up to {leak.max():.2f}", fontsize=6.6)
    ax2.set_yticks([])
    ax2.spines["left"].set_visible(False)
    ax2.grid(axis="y", visible=False)
    ax2.set_xlim(0, 1)
    ax2.set_ylim(-3.6, 3.6)
    ax2.set_xlabel("Time t (s)", labelpad=1)
    save(fig, "t4_geometry")


# --------------------------------------------------------------------------
# Export: snippets, macros, results.json
# --------------------------------------------------------------------------
class ReportStyle(Style):
    """Muted Pygments theme matching the report palette."""
    background_color = "#f7f7f5"
    styles = {
        Comment: "italic #77756e",
        Keyword: "bold #1c5cab",
        Keyword.Constant: "#1c5cab",
        Operator.Word: "bold #1c5cab",
        Name.Builtin: "#6250d6",
        Name.Builtin.Pseudo: "#6250d6",
        Name.Function: "#0b0b0b",
        Name.Class: "#0b0b0b",
        String: "#1a7a52",
        String.Doc: "italic #77756e",
        Number: "#b4501f",
        Operator: "#52514e",
    }


SNIP_START = re.compile(r"^\s*# \[snippet:(task\d)\]\s*$")
SNIP_END = re.compile(r"^\s*# \[/snippet\]\s*$")


def extract_snippets(path: Path) -> dict[str, list[tuple[int, str]]]:
    """Return {snippet id: [(first line number, dedented code), ...]}."""
    lines = path.read_text(encoding="utf-8").splitlines()
    out: dict[str, list[tuple[int, str]]] = {}
    current, start, buf = None, 0, []
    for no, line in enumerate(lines, 1):
        if m := SNIP_START.match(line):
            current, start, buf = m.group(1), no + 1, []
        elif SNIP_END.match(line):
            while buf and not buf[0].strip():
                buf.pop(0)
                start += 1
            code = textwrap.dedent("\n".join(buf)).rstrip()
            out.setdefault(current, []).append((start, code))
            current = None
        elif current:
            buf.append(line)
    return out


def render_snippets() -> dict[str, str]:
    """Highlight every snippet region of this file as LaTeX (fvextra)."""
    style = dict(style=ReportStyle, commandprefix="PY")
    rendered = {"pygments": LatexFormatter(**style).get_style_defs()}
    for sid, regions in extract_snippets(Path(__file__)).items():
        parts = []
        for start, code in regions:
            for i, line in enumerate(code.splitlines()):
                assert line.isascii(), f"{sid}:{start + i} non-ASCII"
                assert len(line) <= SNIPPET_WIDTH, \
                    f"{sid}:{start + i} is {len(line)} chars: {line!r}"
            fmt = LatexFormatter(linenos=True, linenostart=start, **style)
            parts.append(highlight(code, PythonLexer(), fmt))
        rendered[f"snippet_{sid}"] = "\\snippetgap\n".join(parts)
        spans = [(s, s + len(c.splitlines()) - 1) for s, c in regions]
        note(f"snip-{sid}-range", spans,
             ", ".join(f"{a}\u2013{b}" for a, b in spans))
    return rendered


def write_snippets() -> None:
    for name, tex in render_snippets().items():
        (GEN / f"{name}.tex").write_text(tex, encoding="utf-8", newline="\n")


def write_results() -> None:
    versions = {
        "python": platform.python_version(), "numpy": np.__version__,
        "scipy": scipy.__version__, "scikit-learn": sklearn.__version__,
        "matplotlib": matplotlib.__version__, "seaborn": sns.__version__,
    }
    note("versions", versions, ", ".join(
        f"{k}~{v}" for k, v in versions.items()))
    sums = dict(line.split()[::-1] for line in
                (DATA / "SHA256SUMS").read_text(encoding="utf-8").splitlines())
    note("sha-wine", sums["winequality-red.csv"],
         sums["winequality-red.csv"][:12])
    note("sha-geyser", sums["geyser.csv"], sums["geyser.csv"][:12])
    lines = [r"% generated by mlee_assessment.py -- do not edit"]
    for key, text in sorted(TEX.items()):
        lines.append(r"\expandafter\def\csname r@" + key + r"\endcsname{"
                     + text + "}")
    (GEN / "results.tex").write_text("\n".join(lines) + "\n", encoding="utf-8",
                                     newline="\n")
    (ROOT / "results.json").write_text(
        json.dumps(RESULTS, indent=1, sort_keys=True, default=float) + "\n",
        encoding="utf-8", newline="\n")


def main() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    setup_style()
    verify_data()
    task1()
    task2()
    task3()
    task4()
    write_snippets()
    write_results()
    width = max(len(k) for k in TEX)
    for key, text in sorted(TEX.items()):
        if not key.startswith(("t2-mu1", "t2-mu2", "t2-S", "t4-WA")):
            print(f"{key:<{width}}  {text}")


if __name__ == "__main__":
    main()
