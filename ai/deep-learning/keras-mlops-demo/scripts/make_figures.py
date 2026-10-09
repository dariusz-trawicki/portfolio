"""Regenerate the README figures from scratch (light + dark variants).

    uv sync --extra dev --extra figures
    uv run python scripts/make_figures.py

Trains two models (with and without class weights) into a temporary directory,
then renders:
    docs/images/calibration-{light,dark}.png   reliability diagram (Finding 2)
    docs/images/drift-psi-{light,dark}.png     PSI per feature at three drift levels
Takes about 40 seconds on a laptop CPU. Colors come from a validated
colorblind-safe palette (checked in both modes).
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

from mlops_demo.config import FEATURES, GateConfig, TrainConfig  # noqa: E402
from mlops_demo.data import generate_customers  # noqa: E402
from mlops_demo.drift import ALERT, WARN, compare  # noqa: E402
from mlops_demo.predictor import Predictor  # noqa: E402
from mlops_demo.train import run_training  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"
DRIFT_LEVELS = [0.0, 0.4, 0.8]

THEMES = {
    "light": {
        "surface": "#fcfcfb", "text": "#0b0b0b", "text2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "baseline": "#c3c2b7",
        "series": ["#2a78d6", "#eb6834"],              # categorical slots 1-2
        "ordinal": ["#86b6ef", "#2a78d6", "#104281"],  # blue ramp, steps 250/450/650
    },
    "dark": {
        "surface": "#1a1a19", "text": "#ffffff", "text2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "baseline": "#383835",
        "series": ["#3987e5", "#d95926"],
        "ordinal": ["#184f95", "#3987e5", "#9ec5f4"],  # dark: more drift = brighter
    },
}


def style_axes(ax, t, grid_axis="y"):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["baseline"])
        ax.spines[side].set_linewidth(1)
    ax.tick_params(colors=t["muted"], labelcolor=t["text2"], length=0, labelsize=10)
    ax.grid(axis=grid_axis, color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def new_figure(t, size):
    fig, ax = plt.subplots(figsize=size, dpi=200)
    fig.patch.set_facecolor(t["surface"])
    return fig, ax


def title(fig, t, main, sub):
    fig.text(0.02, 0.965, main, color=t["text"], fontsize=13, fontweight="semibold", va="top")
    fig.text(0.02, 0.905, sub, color=t["text2"], fontsize=10, va="top")


def reliability(y, p, n_bins=10, min_n=50):
    bins = np.minimum((p * n_bins).astype(int), n_bins - 1)
    xs, ys = [], []
    for b in range(n_bins):
        m = bins == b
        if m.sum() >= min_n:
            xs.append(p[m].mean())
            ys.append(y[m].mean())
    return np.array(xs), np.array(ys)


def plot_calibration(t, mode, y, curves):
    fig, ax = new_figure(t, (8, 5))
    style_axes(ax, t, grid_axis="both")
    ax.plot([0, 1], [0, 1], color=t["muted"], linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(0.37, 0.45, "perfect calibration", color=t["muted"], fontsize=9, ha="right", va="center")
    for (label, p), color in zip(curves.items(), t["series"]):
        xs, ys = reliability(y, p)
        ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=8,
                markeredgecolor=t["surface"], markeredgewidth=2, label=label)
        ax.annotate(label, (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
                    color=t["text"], fontsize=10, va="center")
    ax.set_xlim(0, 1.15)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("predicted churn probability (bin mean)", color=t["text2"], fontsize=10)
    ax.set_ylabel("observed churn rate", color=t["text2"], fontsize=10)
    leg = ax.legend(loc="upper left", frameon=False, fontsize=10)
    for txt in leg.get_texts():
        txt.set_color(t["text"])
    title(fig, t, "Same AUC, different probabilities",
          "Reliability on 5,000 unseen customers. Class weights push every prediction up; the ranking is unchanged.")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.11)
    fig.savefig(OUT / f"calibration-{mode}.png", facecolor=t["surface"])
    plt.close(fig)


def plot_drift(t, mode, reports):
    names = list(reports[DRIFT_LEVELS[-1]]["features"]) + ["(model score)"]

    def psi_of(rep, name):
        return rep["score"]["psi"] if name == "(model score)" else rep["features"][name]["psi"]

    names.sort(key=lambda n: psi_of(reports[DRIFT_LEVELS[-1]], n))  # largest at the top
    fig, ax = new_figure(t, (8, 5.6))
    style_axes(ax, t, grid_axis="x")
    y = np.arange(len(names))
    h = 0.26
    for i, (level, color) in enumerate(zip(DRIFT_LEVELS, t["ordinal"])):
        vals = [psi_of(reports[level], n) for n in names]
        ax.barh(y + (i - 1) * h, vals, height=h, color=color, edgecolor=t["surface"], linewidth=1,
                label=f"drift {level:.1f}")
        if level == DRIFT_LEVELS[-1]:  # selective direct labels: only the drifted bars that matter
            for yy, v in zip(y + (i - 1) * h, vals):
                if v >= WARN:
                    ax.text(v + 0.008, yy, f"{v:.2f}", color=t["text"], fontsize=9, va="center", zorder=5,
                            bbox=dict(facecolor=t["surface"], edgecolor="none", pad=1.5))
    top = len(names) - 0.4
    for x, label in [(WARN, "warn 0.10"), (ALERT, "alert 0.25")]:
        ax.axvline(x, color=t["text2"], linewidth=1, linestyle=(0, (4, 3)))
        ax.text(x + 0.006, top, label, color=t["text2"], fontsize=9, va="bottom")
    ax.set_yticks(y, names)
    ax.tick_params(axis="y", labelcolor=t["text"])
    ax.set_xlim(0, max(psi_of(reports[DRIFT_LEVELS[-1]], n) for n in names) * 1.15)
    ax.set_ylim(-0.6, len(names) + 0.1)
    ax.set_xlabel("PSI vs training distribution", color=t["text2"], fontsize=10)
    handles, labels = ax.get_legend_handles_labels()
    leg = ax.legend(handles[::-1], labels[::-1], loc="lower right", frameon=False, fontsize=10)
    for txt in leg.get_texts():
        txt.set_color(t["text"])
    title(fig, t, "Drift monitoring: PSI per feature",
          "3,000 simulated requests per drift level. Prices and tenure shift first; the score distribution follows.")
    fig.subplots_adjust(left=0.22, right=0.97, top=0.85, bottom=0.10)
    fig.savefig(OUT / f"drift-psi-{mode}.png", facecolor=t["surface"])
    plt.close(fig)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    OUT.mkdir(parents=True, exist_ok=True)
    gate = GateConfig()
    with tempfile.TemporaryDirectory() as tmp:
        print("training model without class weights...")
        run_training(TrainConfig(), Path(tmp) / "a", tracking_uri=None, gate_cfg=gate)
        print("training model with class weights...")
        run_training(TrainConfig(use_class_weights=True), Path(tmp) / "b", tracking_uri=None, gate_cfg=gate)
        a = Predictor.load(Path(tmp) / "a" / "models" / "v0001")
        b = Predictor.load(Path(tmp) / "b" / "models" / "v0001")

        fresh = generate_customers(5000, seed=123)
        y = fresh["churn"].to_numpy()
        curves = {"no class weights": a.predict_df(fresh[FEATURES]),
                  "class weights": b.predict_df(fresh[FEATURES])}
        for name, p in curves.items():
            print(f"  {name:17} mean prediction {p.mean():.3f} (observed {y.mean():.3f})")

        reports = {}
        for level in DRIFT_LEVELS:
            df = generate_customers(3000, seed=777, drift=level)
            reports[level] = compare(a.reference, df, a.predict_df(df[FEATURES]))
            print(f"  drift {level:.1f}: max PSI {reports[level]['max_psi']:.3f}")

    for mode, t in THEMES.items():
        plot_calibration(t, mode, y, curves)
        plot_drift(t, mode, reports)
    print(f"figures written to {OUT}")


if __name__ == "__main__":
    main()
