"""
momentum_strategy.py
────────────────────
Core engine for the S&P 500 Momentum Strategy.

Strategy:
  - Universe  : Top 100 S&P 500 stocks by market cap (approximate)
  - Signal    : 12-1 month momentum  →  return from (t-252) to (t-21)
                Skipping the last month avoids short-term reversal bias.
  - Portfolio : Equal-weight top-N stocks ranked by momentum score
  - Rebalance : Monthly (last trading day) or Biweekly (every ~10 sessions)
"""

import warnings
warnings.filterwarnings("ignore")
import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

# ── Universe ──────────────────────────────────────────────────────────────────
# ~Top 100 S&P 500 constituents by market capitalisation (as of early 2025)
UNIVERSE: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "BRK-B", "LLY",  "AVGO", "JPM",
    "TSLA", "WMT",  "V",    "XOM",  "UNH",  "MA",   "JNJ",   "COST", "HD",   "PG",
    "ORCL", "BAC",  "ABBV", "KO",   "CVX",  "MRK",  "NFLX",  "CRM",  "AMD",  "PEP",
    "TMO",  "LIN",  "ACN",  "MCD",  "CSCO", "ABT",  "ADBE",  "IBM",  "GE",   "TXN",
    "DHR",  "CAT",  "MS",   "INTU", "NOW",  "AMGN", "ISRG",  "VZ",   "QCOM", "RTX",
    "GS",   "AXP",  "SPGI", "T",    "BLK",  "UBER", "PFE",   "NEE",  "LOW",  "HON",
    "AMAT", "UNP",  "BA",   "DE",   "BKNG", "SYK",  "ETN",   "TJX",  "ADP",  "VRTX",
    "LRCX", "MDT",  "CB",   "PANW", "MU",   "C",    "SCHW",  "ADI",  "MMC",  "PLD",
    "GILD", "REGN", "BSX",  "BMY",  "KLAC", "SO",   "MDLZ",  "DUK",  "WFC",  "HCA",
    "CME",  "ZTS",  "ICE",  "CI",   "EOG",  "USB",  "MCO",   "ITW",  "MMM",  "COP",
]


# ── Data Fetching ─────────────────────────────────────────────────────────────

def _extract_close(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Pull the 'Close' price column out of a yfinance DataFrame regardless of
    which version produced it.

    yfinance column layouts across versions:
      • ≥1.0  multi-ticker : MultiIndex (Price, Ticker)  — raw["Close"] → DataFrame
      • 0.2.x multi-ticker : MultiIndex (Price, Ticker)  — raw["Close"] → DataFrame
      • any   single ticker: flat columns Open/High/…/Close
    """
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        lvl0 = raw.columns.get_level_values(0).unique().tolist()
        lvl1 = raw.columns.get_level_values(1).unique().tolist()

        if "Close" in lvl0:
            # Standard (Price, Ticker) layout — most common
            return raw["Close"].copy()
        elif "Close" in lvl1:
            # Inverted (Ticker, Price) layout — group_by='ticker'
            return raw.xs("Close", axis=1, level=1).copy()
        else:
            raise ValueError(
                f"Cannot find 'Close' in either MultiIndex level.\n"
                f"Level-0 values: {lvl0}\nLevel-1 values: {lvl1}"
            )
    else:
        # Single-ticker flat DataFrame
        if "Close" in raw.columns:
            return raw[["Close"]].copy()
        raise ValueError(f"Unexpected flat columns: {raw.columns.tolist()}")

@st.cache_data(ttl=3600, show_spinner=True)
def fetch_data(tickers: list[str] = UNIVERSE, period: str = "3y") -> tuple[pd.DataFrame, pd.Series]:
    """
    Download daily adjusted closing prices for `tickers` + SPY.

    Robust to:
    • yfinance 0.2.x and 1.x column layout differences
    • Individual tickers that fail (all-NaN → dropped silently)
    • Network hiccups — retries the full batch once, then falls back to
      per-ticker downloads for any that still come back empty.

    Returns
    -------
    prices    : DataFrame[date × ticker]  — universe closing prices
    benchmark : Series[date]              — SPY adjusted closes
    """
    all_tickers = list(dict.fromkeys(tickers + ["SPY"]))
    print(f"[fetch_data] Downloading {len(all_tickers)} tickers (period={period}) …")

    # ── Attempt 1: bulk download ──────────────────────────────────────────────
    raw = yf.download(
        all_tickers,
        period=period,
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    try:
        prices = _extract_close(raw)
    except (ValueError, KeyError) as exc:
        raise RuntimeError(
            f"Failed to parse yfinance output.\n"
            f"Raw columns (first 8): {raw.columns.tolist()[:8]}\n"
            f"Detail: {exc}"
        ) from exc

    # ── Drop completely empty columns (tickers that failed to download) ───────
    failed = prices.columns[prices.isna().all()].tolist()
    if failed:
        print(f"[fetch_data] {len(failed)} tickers returned no data, dropping: {failed[:10]}")
    prices = prices.drop(columns=failed, errors="ignore")

    # ── Attempt 2: retry failed tickers one-by-one ────────────────────────────
    if failed:
        recovered = []
        for tk in failed:
            try:
                single = yf.download(tk, period=period, auto_adjust=True, progress=False)
                col = _extract_close(single)
                if not col.empty and not col.iloc[:, 0].isna().all():
                    col.columns = [tk]
                    recovered.append(col)
            except Exception:
                pass
        if recovered:
            extra = pd.concat(recovered, axis=1)
            prices = pd.concat([prices, extra], axis=1)
            print(f"[fetch_data] Recovered {len(recovered)} ticker(s) via single download.")

    if prices.empty:
        raise RuntimeError(
            "No price data could be downloaded. "
            "Please check your internet connection and that Yahoo Finance is reachable."
        )

    # ── Separate benchmark ────────────────────────────────────────────────────
    benchmark: pd.Series = prices["SPY"].copy() if "SPY" in prices.columns else pd.Series(dtype=float)
    prices = prices.drop(columns=["SPY"], errors="ignore")

    # ── Drop tickers with >20 % missing, forward-fill remaining gaps ──────────
    min_obs = int(len(prices) * 0.80)
    prices = prices.dropna(axis=1, thresh=min_obs).ffill().dropna()

    print(f"[fetch_data] Universe: {len(prices.columns)} stocks | {len(prices)} trading days")
    return prices, benchmark


# ── Signal ────────────────────────────────────────────────────────────────────

def momentum_scores(
    prices: pd.DataFrame,
    date_idx: int,
    lookback: int = 252,
    skip: int = 21,
) -> pd.Series:
    """
    12-1 momentum: cumulative return from (t-lookback) to (t-skip).

    Parameters
    ----------
    prices   : full price history up to the current evaluation date
    date_idx : integer position of the evaluation date in prices.index
    lookback : formation-period length in trading days  (default 252 ≈ 12 mo)
    skip     : recent-reversal skip window in trading days (default 21 ≈ 1 mo)
    """
    if date_idx < lookback:
        return pd.Series(dtype=float)

    start_idx = date_idx - lookback
    end_idx   = date_idx - skip

    if end_idx <= start_idx:
        return pd.Series(dtype=float)

    signal = prices.iloc[end_idx] / prices.iloc[start_idx] - 1.0
    return signal.dropna().sort_values(ascending=False)


# ── Rebalance Calendar ────────────────────────────────────────────────────────

def rebalance_dates(
    index: pd.DatetimeIndex,
    frequency: str = "monthly",
    warmup: int = 252,
) -> pd.DatetimeIndex:
    """
    Return the set of dates on which the portfolio is rebalanced.

    Parameters
    ----------
    index     : the full trading-day DatetimeIndex from the price DataFrame
    frequency : 'monthly' | 'biweekly'
    warmup    : number of leading days needed to compute the momentum signal
    """
    # Series with sequential integers makes resample().last() return the
    # integer position, which is always non-NaN → no dropna needed.
    s = pd.Series(range(len(index)), index=index)

    if frequency == "monthly":
        dates = s.resample("ME").last().index         # last trading day each month
    elif frequency == "biweekly":
        post_warmup = index[warmup:]
        dates = post_warmup[::10]                     # every ~10 sessions ≈ 2 weeks
    else:
        raise ValueError(f"Unknown frequency: {frequency!r}")

    # Only keep dates after we have enough history
    cutoff = index[warmup - 1] if warmup > 0 else index[0]
    return dates[dates > cutoff]


# ── Backtest Engine ───────────────────────────────────────────────────────────

def run_backtest(
    prices: pd.DataFrame,
    benchmark: pd.Series,
    *,
    frequency: str = "monthly",
    top_n: int = 20,
    lookback: int = 252,
    skip: int = 21,
) -> tuple[pd.Series, dict, pd.DataFrame]:
    """
    Vectorised walk-forward backtest.

    Returns
    -------
    port_returns    : daily portfolio returns (equal-weight, long-only)
    holdings_hist   : {date_str: {'tickers': [...], 'scores': {ticker: float}}}
    rebalance_log   : DataFrame summarising each rebalance event
    """
    rb_dates  = set(rebalance_dates(prices.index, frequency, warmup=lookback))
    daily_ret = prices.pct_change()

    port_returns: list[float] = []
    port_dates:   list        = []
    current_holdings: list[str] = []
    holdings_hist: dict = {}
    rebalance_log: list[dict] = []

    for i, date in enumerate(prices.index):

        # ── Rebalance? ────────────────────────────────────────────────────────
        if date in rb_dates and i >= lookback:
            scores = momentum_scores(prices, i, lookback, skip)

            if len(scores) >= top_n:
                prev = set(current_holdings)
                current_holdings = scores.nlargest(top_n).index.tolist()
                new_set = set(current_holdings)

                turnover = len(new_set - prev) / top_n if prev else 1.0

                date_str = str(date.date())
                holdings_hist[date_str] = {
                    "tickers": current_holdings,
                    "scores":  {t: round(float(scores[t]), 6)
                                for t in current_holdings
                                if t in scores.index},
                }

                top5 = ", ".join(current_holdings[:5])
                rebalance_log.append({
                    "Date":         date.strftime("%Y-%m-%d"),
                    "Top 5 Holdings": f"{top5} …",
                    "Avg Momentum": scores[current_holdings].mean(),
                    "Turnover":     turnover,
                    "N Holdings":   len(current_holdings),
                })

        # ── Daily Return ──────────────────────────────────────────────────────
        if current_holdings and i > 0:
            day = daily_ret.loc[date, current_holdings].dropna()
            if len(day) > 0:
                port_returns.append(float(day.mean()))
                port_dates.append(date)

    port_series  = pd.Series(port_returns, index=port_dates, name="Strategy")
    rebalance_df = pd.DataFrame(rebalance_log)

    return port_series, holdings_hist, rebalance_df


# ── Performance Analytics ─────────────────────────────────────────────────────

def compute_metrics(returns: pd.Series, benchmark: pd.Series, rfr: float = 0.05) -> dict:
    """
    Compute comprehensive performance statistics.

    Parameters
    ----------
    returns   : daily strategy returns
    benchmark : daily price series of the benchmark (SPY)
    rfr       : annual risk-free rate (default 5 %)
    """
    n = len(returns)
    if n < 20:
        return {k: float("nan") for k in
                ["total_return", "ann_return", "ann_vol", "sharpe",
                 "max_drawdown", "win_rate", "alpha", "beta",
                 "bench_ann_return", "calmar"]}

    total_ret = float((1.0 + returns).prod() - 1.0)
    ann_ret   = float((1.0 + total_ret) ** (252.0 / n) - 1.0)
    ann_vol   = float(returns.std() * (252 ** 0.5))
    daily_rf  = rfr / 252.0
    sharpe    = float((returns.mean() - daily_rf) / returns.std() * (252 ** 0.5))

    # Drawdown
    cum       = (1.0 + returns).cumprod()
    dd_series = (cum - cum.cummax()) / cum.cummax()
    max_dd    = float(dd_series.min())
    calmar    = ann_ret / abs(max_dd) if max_dd != 0 else float("nan")

    # Monthly win-rate
    monthly   = returns.resample("ME").apply(lambda x: float((1 + x).prod() - 1))
    win_rate  = float((monthly > 0).mean())

    # Alpha & Beta vs benchmark
    bench_ann = float("nan")
    alpha     = float("nan")
    beta      = float("nan")

    if benchmark is not None and len(benchmark) > 0:
        bench_ret = benchmark.pct_change().reindex(returns.index).dropna()
        strat_aligned = returns.reindex(bench_ret.index).dropna()
        bench_ret     = bench_ret.reindex(strat_aligned.index).dropna()

        if len(bench_ret) > 20:
            b_total   = float((1 + bench_ret).prod() - 1)
            bench_ann = float((1 + b_total) ** (252 / len(bench_ret)) - 1)
            alpha     = ann_ret - bench_ann

            cov = np.cov(strat_aligned.values, bench_ret.values)
            beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] != 0 else float("nan")

    return {
        "total_return":    total_ret,
        "ann_return":      ann_ret,
        "ann_vol":         ann_vol,
        "sharpe":          sharpe,
        "max_drawdown":    max_dd,
        "win_rate":        win_rate,
        "alpha":           alpha,
        "beta":            beta,
        "bench_ann_return": bench_ann,
        "calmar":          calmar,
    }


# ── Entry-point ───────────────────────────────────────────────────────────────
# Allows `streamlit run momentum_strategy.py` OR `python momentum_strategy.py`
# to launch the full dashboard defined in app.py.
if __name__ == "__main__":
    import sys as _sys, os as _os, types as _types

    _app = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "app.py")

    # Detect whether we're already inside a Streamlit runtime.
    try:
        from streamlit.runtime import exists as _st_exists
        _in_streamlit = _st_exists()
    except Exception:
        _in_streamlit = False

    if _in_streamlit:
        # `streamlit run momentum_strategy.py` — execute the UI inline so
        # Streamlit's widget/session machinery works without a sub-process.
        # Register this module under its canonical name first, so that
        # `from momentum_strategy import …` inside app.py resolves from cache.
        if "momentum_strategy" not in _sys.modules:
            _mod = _types.ModuleType("momentum_strategy")
            _mod.__dict__.update(
                {k: v for k, v in globals().items() if not k.startswith("_")}
            )
            _sys.modules["momentum_strategy"] = _mod

        with open(_app) as _fh:
            exec(  # noqa: S102
                compile(_fh.read(), _app, "exec"),
                {"__builtins__": __builtins__, "__name__": "__main__", "__file__": _app},
            )
    else:
        # `python momentum_strategy.py` — launch Streamlit as a sub-process.
        import subprocess as _sp
        _sp.run([_sys.executable, "-m", "streamlit", "run", _app], check=False)
