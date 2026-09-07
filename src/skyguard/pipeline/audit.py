"""Data audit — Phase 0 analysis with report generation."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skyguard.config.settings import settings
from skyguard.data.loader import load_raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("skyguard.audit")


def run_audit() -> str:
    df = load_raw(settings.raw_data_path)
    figs_dir = settings.reports_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = ["# SkyGuard Data Audit Report\n"]

    # ── Shape & types ────────────────────────────────────────────────────────
    lines.append("## 1. Dataset Shape")
    lines.append(f"- Rows: {df.shape[0]}")
    lines.append(f"- Columns: {df.shape[1]}")
    lines.append(f"- Columns: {list(df.columns)}\n")

    lines.append("## 2. Data Types")
    for col, dtype in df.dtypes.items():
        lines.append(f"- {col}: {dtype}")
    lines.append("")

    # ── Missing values ───────────────────────────────────────────────────────
    lines.append("## 3. Missing Values")
    missing = df.isna().sum()
    if missing.sum() == 0:
        lines.append("- No missing values detected.\n")
    else:
        for col, n in missing[missing > 0].items():
            lines.append(f"- {col}: {n} ({n/len(df):.1%})")
        lines.append("")

    # ── Duplicates ───────────────────────────────────────────────────────────
    lines.append("## 4. Duplicates")
    dup_rows = df.duplicated().sum()
    dup_ts = df.duplicated(subset=["station_id", "timestamp"]).sum()
    lines.append(f"- Duplicate rows: {dup_rows}")
    lines.append(f"- Duplicate station/timestamp pairs: {dup_ts}\n")

    # ── Timestamp range ──────────────────────────────────────────────────────
    lines.append("## 5. Timestamp Range")
    lines.append(f"- Start: {df['timestamp'].min()}")
    lines.append(f"- End  : {df['timestamp'].max()}")
    lines.append(f"- Span : {df['timestamp'].max() - df['timestamp'].min()}\n")

    # ── Sampling frequency ───────────────────────────────────────────────────
    lines.append("## 6. Sampling Frequency (per station)")
    for station, grp in df.groupby("station_id"):
        diffs = grp["timestamp"].sort_values().diff().dropna()
        mode_freq = diffs.mode()[0] if len(diffs) > 0 else "N/A"
        lines.append(f"- {station}: modal interval = {mode_freq}")
    lines.append("")

    # ── Stations ─────────────────────────────────────────────────────────────
    lines.append("## 7. Stations")
    station_counts = df.groupby("station_id").size()
    for sid, cnt in station_counts.items():
        row = df[df["station_id"] == sid].iloc[0]
        lines.append(
            f"- {sid} ({row['station_name']}): {cnt} obs | "
            f"lat={row['latitude']}, lon={row['longitude']}"
        )
    lines.append("")

    # ── Label distribution ───────────────────────────────────────────────────
    lines.append("## 8. Label Distribution")
    label_counts = df["ground_truth_label"].value_counts()
    for label, cnt in label_counts.items():
        lines.append(f"- {label}: {cnt} ({cnt/len(df):.1%})")
    lines.append("")

    # ── Fault distribution ───────────────────────────────────────────────────
    lines.append("## 9. Fault Description Distribution")
    fault_counts = df["fault_description"].value_counts()
    for fault, cnt in fault_counts.items():
        lines.append(f"- {fault}: {cnt}")
    lines.append("")

    # ── Fault by station ─────────────────────────────────────────────────────
    lines.append("## 10. Fault Distribution by Station")
    fault_by_station = (
        df[df["ground_truth_label"] != "NORMAL"]
        .groupby(["station_id", "ground_truth_label"])
        .size()
        .reset_index(name="count")
    )
    lines.append(fault_by_station.to_string(index=False))
    lines.append("")

    # ── Numerical distributions ──────────────────────────────────────────────
    sensor_cols = ["temperature_c", "relative_humidity_pct", "pressure_hpa",
                   "wind_speed_kmh", "rainfall_mm"]
    lines.append("## 11. Numerical Distributions")
    desc = df[sensor_cols].describe().round(3)
    lines.append(desc.to_string())
    lines.append("")

    # ── Physical violations ──────────────────────────────────────────────────
    lines.append("## 12. Physical Bound Violations")
    bounds = settings.physical_bounds
    for col, (lo, hi) in bounds.items():
        if col in df.columns:
            n = int(((df[col] < lo) | (df[col] > hi)).sum())
            lines.append(f"- {col} outside [{lo}, {hi}]: {n} rows")
    lines.append("")

    # ── Correlation matrix ───────────────────────────────────────────────────
    lines.append("## 13. Correlation Matrix (sensor columns)")
    corr = df[sensor_cols].corr().round(3)
    lines.append(corr.to_string())
    lines.append("")

    # ── Temporal continuity ──────────────────────────────────────────────────
    lines.append("## 14. Temporal Continuity")
    for station, grp in df.groupby("station_id"):
        grp_s = grp.sort_values("timestamp")
        gaps = grp_s["timestamp"].diff().dropna()
        large_gaps = gaps[gaps > pd.Timedelta("1h")]
        lines.append(f"- {station}: {len(large_gaps)} gaps > 1h")
    lines.append("")

    # ── Spatial distances ────────────────────────────────────────────────────
    lines.append("## 15. Spatial Distances Between Stations (km)")
    from skyguard.features.spatial import build_station_coords, haversine_km
    coords = build_station_coords(df)
    station_list = list(coords.keys())
    for i, s1 in enumerate(station_list):
        for s2 in station_list[i + 1:]:
            d = haversine_km(*coords[s1], *coords[s2])
            lines.append(f"- {s1} <-> {s2}: {d:.2f} km")
    lines.append("")

    # ── Key findings ─────────────────────────────────────────────────────────
    lines.append("## 16. Key Findings & Implications")
    lines.append("- Dataset is small (504 rows) and highly imbalanced (NORMAL=92.7%).")
    lines.append("- Only 3 stations, all in Chennai, India — very close spatially.")
    lines.append("- Hourly data over 7 days; no temporal gaps detected.")
    lines.append("- Drift fault (13 obs) and Freeze fault (11 obs) may support limited supervised classification.")
    lines.append("- Spike fault (1 obs) — supervised classification NOT feasible; use rule-based detection.")
    lines.append("- Thunderstorm events affect all 3 stations simultaneously — spatial consistency is a strong signal.")
    lines.append("- Pressure spike (850 hPa) is a clear physical violation — easily detectable by rules.")
    lines.append("- Humidity freeze (constant 62.4%) is detectable by zero-variance rule.")
    lines.append("- Temperature drift shows persistent positive deviation vs. neighbors — spatial residual is key.")
    lines.append("")

    # ── Plots ────────────────────────────────────────────────────────────────
    _plot_label_distribution(df, figs_dir)
    _plot_sensor_distributions(df, sensor_cols, figs_dir)
    _plot_temporal_series(df, sensor_cols, figs_dir)
    _plot_correlation(df, sensor_cols, figs_dir)

    report_text = "\n".join(lines)
    report_path = settings.reports_dir / "data_audit.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    logger.info("Data audit report saved to %s", report_path)
    return report_text


def _plot_label_distribution(df: pd.DataFrame, figs_dir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    label_counts = df["ground_truth_label"].value_counts()
    label_counts.plot(kind="bar", ax=axes[0], color=["steelblue", "orange", "red"])
    axes[0].set_title("Label Distribution")
    axes[0].set_ylabel("Count")
    axes[0].tick_params(axis="x", rotation=30)

    fault_counts = df[df["fault_description"] != "None"]["fault_description"].value_counts()
    fault_counts.plot(kind="barh", ax=axes[1], color="coral")
    axes[1].set_title("Fault Type Distribution")
    plt.tight_layout()
    fig.savefig(figs_dir / "label_distribution.png", dpi=100)
    plt.close(fig)


def _plot_sensor_distributions(df: pd.DataFrame, sensor_cols: list[str], figs_dir: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    colors = {"NORMAL": "steelblue", "SENSOR_FAULT": "red", "GENUINE_EXTREME": "orange"}
    for i, col in enumerate(sensor_cols):
        for label, grp in df.groupby("ground_truth_label"):
            axes[i].hist(grp[col].dropna(), bins=30, alpha=0.5,
                        label=label, color=colors.get(label, "gray"))
        axes[i].set_title(col)
        axes[i].legend(fontsize=7)
    axes[-1].set_visible(False)
    plt.tight_layout()
    fig.savefig(figs_dir / "sensor_distributions.png", dpi=100)
    plt.close(fig)


def _plot_temporal_series(df: pd.DataFrame, sensor_cols: list[str], figs_dir: Path) -> None:
    for col in ["temperature_c", "pressure_hpa", "relative_humidity_pct"]:
        fig, ax = plt.subplots(figsize=(14, 4))
        for station, grp in df.groupby("station_id"):
            grp_s = grp.sort_values("timestamp")
            ax.plot(grp_s["timestamp"], grp_s[col], label=station, alpha=0.8)
        # Mark faults
        faults = df[df["ground_truth_label"] == "SENSOR_FAULT"]
        ax.scatter(faults["timestamp"], faults[col], color="red", s=20, zorder=5, label="FAULT")
        extremes = df[df["ground_truth_label"] == "GENUINE_EXTREME"]
        ax.scatter(extremes["timestamp"], extremes[col], color="orange", s=20, zorder=5, label="EXTREME")
        ax.set_title(f"{col} over time")
        ax.legend(fontsize=7)
        plt.tight_layout()
        fig.savefig(figs_dir / f"timeseries_{col}.png", dpi=100)
        plt.close(fig)


def _plot_correlation(df: pd.DataFrame, sensor_cols: list[str], figs_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    corr = df[sensor_cols].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
    ax.set_title("Sensor Correlation Matrix")
    plt.tight_layout()
    fig.savefig(figs_dir / "correlation_matrix.png", dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    report = run_audit()
    print(report)
