# 📈 S&P 500 Momentum Strategy Dashboard

A production-grade momentum trading strategy built on daily closing prices of the
100 largest S&P 500 companies, with an interactive Dash dashboard.

---

## Strategy Overview

| Parameter       | Default      | Options                      |
|-----------------|--------------|------------------------------|
| Universe        | Top 100 S&P 500 by mkt cap | Fixed (see `UNIVERSE` in `momentum_strategy.py`) |
| Signal          | 12-1 momentum | 6-mo, 9-mo, 12-mo lookback   |
| Skip window     | 21 days (1 mo) | Fixed — avoids reversal bias |
| Portfolio       | Equal-weight, long-only | Top-N ranked by signal |
| Rebalancing     | Monthly       | Monthly / Biweekly           |
| Benchmark       | SPY (S&P 500 ETF) | —                        |

**12-1 Momentum formula:**

```
score(t) = Price(t - 21) / Price(t - 252) - 1
```

Skipping the most-recent month avoids known short-term reversal effects.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the dashboard

```bash
streamlit run app.py
```

opens automatically **http://localhost:8050** in your browser.

### 3. Using the dashboard

1. Adjust the four controls in the top panel:
   - **Rebalancing Frequency** — Monthly or Biweekly
   - **Momentum Lookback** — 6, 9, or 12 months
   - **Portfolio Size** — how many top-ranked stocks to hold (10–40)
   - **Historical Period** — how far back to download and backtest

2. Click **▶ RUN BACKTEST** — data downloads once and is cached in memory.

3. Explore the six panels:
   - **KPIs** — Total Return, Ann. Return, Sharpe, Max Drawdown, Volatility, Alpha
   - **Cumulative Performance** — Strategy vs SPY equity curve
   - **Current Holdings** — ranked table of the current portfolio
   - **Momentum Scores** — bar chart of each holding's signal
   - **Drawdown** — underwater equity curve
   - **Monthly Returns Heatmap** — calendar view of monthly P&L
   - **Rebalancing History** — every past rebalance with turnover stats

---

## File Structure

```
momentum_dashboard/
├── app.py                  # Dash dashboard + callbacks
├── momentum_strategy.py    # Strategy engine (data, signal, backtest, metrics)
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## Extending the Strategy

### Add new signals
Edit `momentum_strategy.py` → `momentum_scores()`. You can replace or augment the
12-1 signal with anything computable from the price DataFrame (e.g., risk-adjusted
momentum, residual momentum, or a combination).

### Add position sizing
Replace equal-weighting in `run_backtest()` (the `day.mean()` line) with any
weighting scheme — inverse volatility, signal-proportional, etc.

### Add short side
After selecting top-N longs, select bottom-N shorts and subtract their returns
with the appropriate weight.

### Add transaction costs
Insert a cost term inside `run_backtest()` on each rebalance date based on
`turnover * cost_per_unit`.

---

## Notes

- Data is fetched from **Yahoo Finance** via `yfinance`. Prices are adjusted for
  splits and dividends (`auto_adjust=True`).
- The first download for a given period takes ~30–60 seconds (100 tickers).
  Subsequent runs with the same period use the in-memory cache instantly.
- The backtest is **not** adjusted for transaction costs, slippage, or taxes.
- Past performance does not indicate future results.
