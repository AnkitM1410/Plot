"""
BTC 4-Year Cycle Plot Generator & Twitter Bot
==============================================
Downloads BTC historical data from Kaggle, generates two cycle plots
(linear overlay and polar), and tweets them as a single tweet with
both images attached.

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
from requests_oauthlib import OAuth1
from datetime import datetime


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


# ---------------------------------------------------------------------------
# 3. TWITTER / X UPLOAD
# ---------------------------------------------------------------------------

def upload_image_to_x(
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    image_path: str,
) -> str | None:
    """Upload a local image to Twitter and return the media_id_string."""
    auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
    url = "https://upload.twitter.com/1.1/media/upload.json"
    params = {"media_category": "tweet_image"}

    with open(image_path, "rb") as img:
        files = {"media": img.read()}

    response = requests.post(url, params=params, files=files, auth=auth)

    if response.status_code in (200, 201, 202):
        media_id = response.json().get("media_id_string")
        print(f"Image uploaded: {image_path} -> media_id={media_id}")
        return media_id
    else:
        print(f"Image upload failed ({response.status_code}): {response.text}")
        return None


def post_tweet(
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    text: str,
    media_ids: list[str],
) -> bool:
    """Post a tweet with attached media."""
    url = "https://api.twitter.com/2/tweets"
    auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)

    payload = {"text": text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}

    response = requests.post(url, json=payload, auth=auth)

    if response.status_code == 201:
        tweet_data = response.json()
        print(f"Tweet posted successfully: {tweet_data}")
        return True
    else:
        print(f"Tweet failed ({response.status_code}): {response.text}")
        return False


# ---------------------------------------------------------------------------
# 4. MAIN ORCHESTRATOR
# ---------------------------------------------------------------------------

def main():
    print(f"=== BTC Plot & Tweet Bot — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    # --- Download & process data ---
    csv_path = download_kaggle_data(output_dir=".")
    df = process_data(csv_path)
    df = prepare_cycle_columns(df)

    latest_price = df["price"].iloc[-1]
    latest_date = df["datetime"].iloc[-1].strftime("%b %d, %Y")

    # --- Generate plots ---
    linear_path = generate_linear_plot(df, "btc_4y_linear.png")
    polar_path = generate_polar_plot(df, "btc_4y_polar.png")

    # --- Twitter credentials ---
    consumer_key = os.environ.get("X_CONSUMER_KEY")
    consumer_secret = os.environ.get("X_CONSUMER_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        print("ERROR: Twitter/X credentials not set. Skipping tweet.")
        sys.exit(1)

    # --- Upload images ---
    media_id_1 = upload_image_to_x(
        consumer_key, consumer_secret, access_token, access_token_secret, linear_path
    )
    media_id_2 = upload_image_to_x(
        consumer_key, consumer_secret, access_token, access_token_secret, polar_path
    )

    media_ids = [mid for mid in [media_id_1, media_id_2] if mid is not None]

    if not media_ids:
        print("ERROR: No images were uploaded. Aborting tweet.")
        sys.exit(1)

    # --- Tweet ---
    tweet_text = os.environ.get(
        "TWEET_TEXT",
        f"\U0001f4ca BTC 4-Year Cycle Update | ${latest_price:,.0f} | {latest_date}"
    )

    success = post_tweet(
        consumer_key, consumer_secret, access_token, access_token_secret,
        tweet_text, media_ids
    )

    if not success:
        sys.exit(1)

    print("Done!")


if __name__ == "__main__":
    main()
