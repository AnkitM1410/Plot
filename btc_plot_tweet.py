"""
BTC 4-Year Cycle Plot Generator
===============================
Downloads BTC historical data from Kaggle, generates two cycle plots
(linear overlay and polar), and outputs them along with index.html for GitHub Pages.

Designed to run daily via GitHub Actions cron job.
"""

import os
import sys
import subprocess
import zipfile
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for CI
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator
import requests
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# 1. DATA DOWNLOAD & PROCESSING
# ---------------------------------------------------------------------------

def download_kaggle_data(output_dir: str = ".") -> str:
    """Download BTC historical data from Kaggle and return the CSV path."""
    zip_path = os.path.join(output_dir, "bitcoin-historical-data.zip")
    csv_path = os.path.join(output_dir, "btcusd_1-min_data.csv")

    kaggle_username = os.environ.get("KAGGLE_USERNAME")
    kaggle_key = os.environ.get("KAGGLE_KEY")

    if not kaggle_username or not kaggle_key:
        print("ERROR: KAGGLE_USERNAME and KAGGLE_KEY must be set.")
        sys.exit(1)

    # Write kaggle.json so the kaggle CLI / API can authenticate
    kaggle_dir = os.path.expanduser("~/.kaggle")
    os.makedirs(kaggle_dir, exist_ok=True)
    kaggle_json_path = os.path.join(kaggle_dir, "kaggle.json")
    with open(kaggle_json_path, "w") as f:
        f.write(f'{{"username":"{kaggle_username}","key":"{kaggle_key}"}}')
    os.chmod(kaggle_json_path, 0o600)

    # Download via curl (same as the notebook)
    print("Downloading BTC data from Kaggle...")
    subprocess.run([
        "curl", "-L",
        "-u", f"{kaggle_username}:{kaggle_key}",
        "-o", zip_path,
        "https://www.kaggle.com/api/v1/datasets/download/mczielinski/bitcoin-historical-data"
    ], check=True)

    # Unzip
    print("Extracting data...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(output_dir)

    if not os.path.exists(csv_path):
        print(f"ERROR: Expected CSV not found at {csv_path}")
        sys.exit(1)

    return csv_path


def process_data(csv_path: str) -> pd.DataFrame:
    """Read 1-min BTC data and resample to daily max price."""
    print("Processing data...")
    btcusd_1_min_df = pd.read_csv(csv_path)
    btcusd_1_min_df["datetime"] = pd.to_datetime(
        btcusd_1_min_df["Timestamp"], unit="s"
    )
    btcusd_1_min_df["price"] = btcusd_1_min_df[
        ["Open", "High", "Low", "Close"]
    ].max(axis=1)

    df = (
        btcusd_1_min_df.set_index("datetime")["price"]
        .resample("D")
        .max()
        .to_frame(name="price")
        .reset_index()
    )
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df


# ---------------------------------------------------------------------------
# 2. PLOT GENERATION (2nd & 3rd from notebook)
# ---------------------------------------------------------------------------

HALVING_DATES = [
    pd.to_datetime("2012-11-28"),
    pd.to_datetime("2016-07-09"),
    pd.to_datetime("2020-05-11"),
    pd.to_datetime("2024-04-20"),
]


def prepare_cycle_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add cycle-related columns to df."""
    start_date = df["datetime"].min()
    period_days = int(365.25 * 4)

    df["days"] = (df["datetime"] - start_date).dt.days
    df["cycle"] = df["days"] // period_days
    df["days_in_cycle"] = df["days"] % period_days
    return df


def generate_linear_plot(df: pd.DataFrame, output_path: str) -> str:
    """
    2nd plot from notebook — Linear overlay of 4-year cycles with
    ATH, ATL, and halving markers.
    """
    start_date = df["datetime"].min()
    period_days = int(365.25 * 4)

    fig, ax = plt.subplots(figsize=(16, 8), dpi=200)

    for cycle, group in df.groupby("cycle"):
        # Plot cycle line
        ax.plot(
            group["days_in_cycle"] / 365.25,
            group["price"],
            label="",
            color="orange",
        )

        # ATH within this cycle
        ath_idx = group["price"].idxmax()
        ath_row = group.loc[ath_idx]
        ax.scatter(
            ath_row["days_in_cycle"] / 365.25,
            ath_row["price"],
            c="darkblue",
            s=80,
            label="ATH" if cycle == 0 else "",
            zorder=3,
        )
        ax.annotate(
            f"${ath_row['price']:,.0f}",
            (ath_row["days_in_cycle"] / 365.25, ath_row["price"]),
            textcoords="offset points",
            xytext=(8, 0),
            ha="left",
            fontsize=7,
            color="darkblue",
            bbox=dict(
                boxstyle="round,pad=0.2",
                facecolor="white",
                alpha=0.7,
                edgecolor="none",
            ),
        )

        # ATL = lowest after ATH within this cycle
        after_ath = group[group["datetime"] > ath_row["datetime"]]
        if not after_ath.empty:
            atl_idx = after_ath["price"].idxmin()
            atl_row = after_ath.loc[atl_idx]
            ax.scatter(
                atl_row["days_in_cycle"] / 365.25,
                atl_row["price"],
                c="red",
                s=80,
                label="ATL (% drop after ATH)" if cycle == 0 else "",
                zorder=3,
            )
            pct_drop = (
                (atl_row["price"] - ath_row["price"]) / ath_row["price"]
            ) * 100
            ax.annotate(
                f"${atl_row['price']:,.0f} ({pct_drop:.1f}%)",
                (atl_row["days_in_cycle"] / 365.25, atl_row["price"]),
                textcoords="offset points",
                xytext=(8, 0),
                ha="left",
                fontsize=7,
                color="red",
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="white",
                    alpha=0.7,
                    edgecolor="none",
                ),
            )

    # Plot halving points
    for i, d in enumerate(HALVING_DATES):
        if d >= start_date and d <= df["datetime"].max():
            day_val = (d - start_date).days
            cycle_num = day_val // period_days
            day_in_cycle = day_val % period_days
            year_in_cycle = day_in_cycle / 365.25
            nearest_idx = df.loc[df["datetime"].sub(d).abs().idxmin()].name
            halving_price = df.loc[nearest_idx, "price"]
            ax.scatter(
                year_in_cycle,
                halving_price,
                c="blue",
                s=80,
                marker="o",
                label="Halving" if i == 0 else "",
                zorder=3,
            )
            ax.annotate(
                f"${halving_price:,.0f}",
                (year_in_cycle, halving_price),
                textcoords="offset points",
                xytext=(8, 0),
                ha="left",
                fontsize=7,
                color="blue",
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="white",
                    alpha=0.7,
                    edgecolor="none",
                ),
            )

    # Log scale
    ax.set_yscale("log")
    ax.set_xlim(0, 4)
    ax.set_xticks([0, 1, 2, 3, 4])
    ax.set_xticklabels(
        [
            "2012,16,20,24",
            "2013,17,21,25",
            "2014,18,22,26",
            "2015,19,23,27",
            "2016,20,24,28",
        ]
    )

    yticks = [1, 10, 100, 1000, 10000, 100000, 1000000]
    ytick_labels = ["", "$10", "$100", "$1k", "$10k", "$100k", "$1M"]
    ax.set_yticks(yticks)
    ax.set_yticklabels(ytick_labels)

    ax.yaxis.set_major_locator(
        LogLocator(base=10.0, subs=[1.0], numticks=10)
    )
    ax.yaxis.set_minor_locator(
        LogLocator(base=10.0, subs=np.arange(2, 10) * 0.1, numticks=10)
    )

    ax.grid(
        which="major", color="gray", linestyle="--", linewidth=0.8, alpha=0.7
    )
    ax.grid(
        which="minor",
        color="lightgray",
        linestyle="--",
        linewidth=0.5,
        alpha=0.5,
    )

    for year in [1, 2, 3, 4]:
        ax.axvline(year, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    for year in range(4):
        for quarter in [0.25, 0.5, 0.75]:
            ax.axvline(
                year + quarter,
                color="lightgray",
                linestyle="-",
                linewidth=0.8,
                alpha=0.7,
            )

    ax.set_title("BTC 4Yr Cycles with ATH, Post-ATH ATL & Halvings")
    plt.legend()
    plt.savefig(output_path, dpi=400, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Linear plot saved to {output_path}")
    return output_path


def generate_polar_plot(df: pd.DataFrame, output_path: str) -> str:
    """
    3rd plot from notebook — Polar cycle plot with ATH, ATL, and halvings.
    """
    start_date = df["datetime"].min()
    period_days = int(365.25 * 4)
    CYCLE_RAD = 2 * np.pi

    fig = plt.figure(figsize=(10, 10), dpi=200)
    ax = fig.add_subplot(111, projection="polar")

    for cycle, group in df.groupby("cycle"):
        theta = (group["days_in_cycle"] / period_days) * CYCLE_RAD
        r = group["price"].values

        ax.plot(theta, r, color="orange", lw=1.2)

        # ATH
        ath_idx = group["price"].idxmax()
        ath_row = group.loc[ath_idx]
        ath_t = (ath_row["days_in_cycle"] / period_days) * CYCLE_RAD
        ath_r = ath_row["price"]
        ax.scatter(
            ath_t,
            ath_r,
            c="darkblue",
            s=80,
            zorder=3,
            label="ATH" if cycle == 0 else "",
        )
        ax.annotate(
            f"${ath_r:,.0f}",
            (ath_t, ath_r),
            xytext=(5, 5),
            textcoords="offset points",
            ha="left",
            fontsize=7,
            color="darkblue",
            bbox=dict(
                boxstyle="round,pad=0.2",
                facecolor="white",
                alpha=0.7,
                edgecolor="none",
            ),
        )

        # ATL (after ATH)
        after_ath = group[group["datetime"] > ath_row["datetime"]]
        if not after_ath.empty:
            atl_idx = after_ath["price"].idxmin()
            atl_row = after_ath.loc[atl_idx]
            atl_t = (atl_row["days_in_cycle"] / period_days) * CYCLE_RAD
            atl_r = atl_row["price"]
            ax.scatter(
                atl_t,
                atl_r,
                c="red",
                s=80,
                zorder=3,
                label="ATL (after ATH)" if cycle == 0 else "",
            )
            ax.annotate(
                f"${atl_r:,.0f}",
                (atl_t, atl_r),
                xytext=(5, 5),
                textcoords="offset points",
                ha="left",
                fontsize=7,
                color="red",
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="white",
                    alpha=0.7,
                    edgecolor="none",
                ),
            )

    # Halvings
    for i, d in enumerate(HALVING_DATES):
        if d < df["datetime"].min() or d > df["datetime"].max():
            continue
        days_since = (d - start_date).days
        t = (days_since % period_days) / period_days * CYCLE_RAD
        nearest_price = df.loc[
            df["datetime"].sub(d).abs().idxmin(), "price"
        ]
        ax.scatter(
            t,
            nearest_price,
            c="blue",
            s=80,
            marker="o",
            zorder=3,
            label="Halving" if i == 0 else "",
        )
        ax.annotate(
            f"${nearest_price:,.0f}",
            (t, nearest_price),
            xytext=(5, 5),
            textcoords="offset points",
            ha="left",
            fontsize=7,
            color="blue",
            bbox=dict(
                boxstyle="round,pad=0.2",
                facecolor="white",
                alpha=0.7,
                edgecolor="none",
            ),
        )

    # Log radial axis
    ax.set_theta_direction(-1)
    ax.set_theta_zero_location("W")
    ax.set_yscale("log")
    ax.set_ylim(bottom=1, top=1e6)

    yticks = [1, 10, 100, 1_000, 10_000, 100_000, 1_000_000]
    ax.set_yticks(yticks)
    ax.set_yticklabels(["", "$10", "$100", "$1k", "$10k", "$100k", "$1M"])

    ax.set_xticks(np.linspace(0, CYCLE_RAD, 5))
    ax.set_xticklabels(["0 y", "1 y", "2 y", "3 y", "4 y"])
    ax.grid(True, which="major", alpha=0.7, lw=0.8, color="gray")

    ax.set_title(
        "BTC 4-Year Polar Cycles \u2013 ATH / ATL / Halvings", pad=20
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1))

    plt.savefig(output_path, dpi=400, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Polar plot saved to {output_path}")
    return output_path


def generate_index_html(output_path: str = "index.html", generated_time: str = None, trigger_type: str = "Manual Trigger") -> str:
    """Generate HTML with consistent, responsive image display width."""
    if not generated_time:
        generated_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin 4-Year Cycle Analysis</title>
    <style>
        img {{
            width: 100%;
            height: auto;
            display: block;
        }}
    </style>
</head>
<body>
    <p>Last updated: {generated_time} | Source: {trigger_type}</p>
    <h1>Bitcoin 4-Year Cycle Analysis</h1>
    <p><img src="btc_4y_linear.png" alt="BTC 4-Year Cycle Overlay (Log Scale)"></p>
    <p><img src="btc_4y_polar.png" alt="BTC 4-Year Cycle Polar Projection"></p>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Index HTML generated at {output_path} (Trigger: {trigger_type})")
    return output_path


# ---------------------------------------------------------------------------
# 3. MAIN ORCHESTRATOR
# ---------------------------------------------------------------------------

def main():
    gen_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    event_name = os.environ.get("GITHUB_EVENT_NAME", "").strip().lower()
    if event_name == "schedule":
        trigger_type = "Scheduled Run"
    elif event_name == "workflow_dispatch":
        trigger_type = "Manual Trigger"
    elif event_name:
        trigger_type = f"Trigger: {event_name.capitalize()}"
    else:
        trigger_type = "Manual Trigger"

    print(f"=== BTC Plot Generator — {gen_time_str} | {trigger_type} ===")

    # --- Download & process data ---
    csv_path = download_kaggle_data(output_dir=".")
    df = process_data(csv_path)
    df = prepare_cycle_columns(df)

    latest_price = df["price"].iloc[-1]
    latest_date = df["datetime"].iloc[-1].strftime("%b %d, %Y")
    print(f"Latest BTC Price: ${latest_price:,.0f} on {latest_date}")

    # --- Generate plots ---
    linear_path = generate_linear_plot(df, "btc_4y_linear.png")
    polar_path = generate_polar_plot(df, "btc_4y_polar.png")

    # --- Generate index.html ---
    generate_index_html("index.html", gen_time_str, trigger_type=trigger_type)

    print("All plots and index.html generated successfully!")


if __name__ == "__main__":
    main()
