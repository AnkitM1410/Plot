# BTC 4-Year Cycle Plot & Tweet Bot

Automated daily Bitcoin 4-year cycle chart generator that tweets updated plots to Twitter/X.

## What it does

1. **Downloads** the latest BTC/USD 1-minute historical data from Kaggle
2. **Processes** and resamples it to daily max prices
3. **Generates** two chart types:
   - **Linear overlay** — All 4-year cycles overlaid on log scale with ATH, post-ATH ATL, and halving markers
   - **Polar plot** — Same data in a polar/circular projection
4. **Tweets** both charts as a single post to Twitter/X

## Setup

### GitHub Secrets (Required)

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret Name | Description |
|---|---|
| `KAGGLE_USERNAME` | Your Kaggle username |
| `KAGGLE_KEY` | Your Kaggle API key (from kaggle.com/settings) |
| `X_CONSUMER_KEY` | Twitter/X API Consumer Key (API Key) |
| `X_CONSUMER_SECRET` | Twitter/X API Consumer Secret (API Secret) |
| `X_ACCESS_TOKEN` | Twitter/X Access Token |
| `X_ACCESS_TOKEN_SECRET` | Twitter/X Access Token Secret |

### GitHub Variables (Optional)

Go to **Settings** → **Secrets and variables** → **Actions** → **Variables** tab:

| Variable Name | Description | Default |
|---|---|---|
| `TWEET_TEXT` | Custom tweet text (overrides auto-generated) | Auto-generated with price & date |

## Schedule

The bot runs daily at **03:00 UTC** (08:30 IST) via GitHub Actions cron.  
You can also trigger it manually from the **Actions** tab → **Daily BTC Plot & Tweet** → **Run workflow**.
