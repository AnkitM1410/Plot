# BTC 4-Year Cycle Plot & GitHub Pages

Automated daily Bitcoin 4-year cycle chart generator deployed directly to GitHub Pages.

## What it does

1. **Downloads** the latest BTC/USD 1-minute historical data from Kaggle
2. **Processes** and resamples it to daily max prices
3. **Generates** two chart types:
   - **Linear overlay** — All 4-year cycles overlaid on log scale with ATH, post-ATH ATL, and halving markers
   - **Polar plot** — Same data in a polar/circular projection
4. **Builds `index.html`** displaying the generation date and timestamp at the top followed by both charts
5. **Deploys** the charts and `index.html` to **GitHub Pages**
6. **Stores workflow artifacts** with a **15-day retention period**

## Setup

### 1. GitHub Secrets (Required)

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret Name | Description |
|---|---|
| `KAGGLE_USERNAME` | Your Kaggle username |
| `KAGGLE_KEY` | Your Kaggle API key (from kaggle.com/settings) |

### 2. Enable GitHub Pages

Go to your repo → **Settings** → **Pages**:
- Under **Build and deployment** → **Source**, select **GitHub Actions**.

## Schedule

The workflow runs daily at **03:00 UTC** (08:30 IST) via GitHub Actions cron.  
You can also trigger it manually from the **Actions** tab → **Daily Cycle Plots & GitHub Pages Deploy** → **Run workflow**.
