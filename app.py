"""
app.py  —  S&P 500 Momentum Strategy  ·  Streamlit Dashboard
─────────────────────────────────────────────────────────────
Run with:
    streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from momentum_strategy import (
    UNIVERSE,
    compute_metrics,
    fetch_data,
    run_backtest,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Momentum Strategy",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ─────────────────────────────────────────────────────────────
BG      = "#03070e"
SURFACE = "#08111d"
CARD    = "#0c1a2b"
BORDER  = "#112234"

CYAN    = "#00e5ff"
GREEN   = "#00ff9d"
RED     = "#ff3d71"
AMBER   = "#ffaa00"
PURPLE  = "#a855f7"
MUTED   = "#4a6880"
TEXT    = "#8fb8d8"
BRIGHT  = "#c8e6f8"

PLOTLY = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family="'JetBrains Mono', monospace", size=11),
    margin=dict(l=12, r=12, t=28, b=12),
    hovermode="x unified",
    hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER, font_color=BRIGHT),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
    xaxis=dict(gridcolor=BORDER, gridwidth=0.5, linecolor="#1a3248", zeroline=False),
    yaxis=dict(gridcolor=BORDER, gridwidth=0.5, linecolor="#1a3248", zeroline=False),
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600&family=Rajdhani:wght@500;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {{
    background: {BG};
    color: {TEXT};
    font-family: 'JetBrains Mono', monospace;
}}
[data-testid="stSidebar"] {{
    background: {SURFACE} !important;
    border-right: 1px solid {BORDER};
}}
[data-testid="stSidebar"] * {{ color: {TEXT} !important; }}
.block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}

.kpi-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 14px 18px;
    height: 90px;
}}
.kpi-label {{
    font-family: 'Rajdhani', sans-serif;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: {MUTED};
    margin-bottom: 6px;
}}
.kpi-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 600;
    line-height: 1;
}}
.kpi-green  {{ color: {GREEN}; }}
.kpi-red    {{ color: {RED}; }}
.kpi-cyan   {{ color: {CYAN}; }}
.kpi-amber  {{ color: {AMBER}; }}
.kpi-purple {{ color: {PURPLE}; }}

.section-hdr {{
    font-family: 'Rajdhani', sans-serif;
    font-size: 11px;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: {MUTED};
    border-bottom: 1px solid {BORDER};
    padding-bottom: 6px;
    margin-bottom: 8px;
}}

#MainMenu, footer, header {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def kpi(label, value, color_cls="kpi-cyan"):
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value {color_cls}">{value}</div></div>',
        unsafe_allow_html=True,
    )

def section(title):
    st.markdown(f'<div class="section-hdr">{title}</div>', unsafe_allow_html=True)

def pct(v, sign=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{'+' if sign and v > 0 else ''}{v:.1%}"

def num(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.{d}f}"


@st.cache_data(show_spinner="Downloading price data from Yahoo Finance…")
def load_data(period):
    return fetch_data(UNIVERSE, period=period)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div style="font-family:Rajdhani,sans-serif;font-size:20px;font-weight:700;'
        f'color:{BRIGHT};letter-spacing:3px;margin-bottom:4px;">▲ MOMENTUM</div>'
        f'<div style="font-size:10px;color:{MUTED};letter-spacing:1px;margin-bottom:20px;">'
        f'S&P 500 · TOP 100 LARGE-CAP</div>',
        unsafe_allow_html=True,
    )

    frequency = st.selectbox(
        "REBALANCING FREQUENCY",
        options=["monthly", "biweekly"],
        format_func=lambda x: "📅  Monthly (last trading day)" if x == "monthly"
                              else "📅  Biweekly (~10 sessions)",
    )
    lookback = st.selectbox(
        "MOMENTUM LOOKBACK",
        options=[126, 189, 252],
        index=2,
        format_func=lambda x: {126:"6 Months",189:"9 Months",252:"12 Months"}[x],
    )
    top_n = st.slider("PORTFOLIO SIZE  (Top-N)", min_value=10, max_value=40, step=5, value=20)
    period = st.selectbox(
        "HISTORICAL PERIOD",
        options=["2y","3y","5y"],
        index=1,
        format_func=lambda x: {"2y":"2 Years","3y":"3 Years","5y":"5 Years"}[x],
    )
    st.markdown("<br>", unsafe_allow_html=True)
    run = st.button("▶  RUN BACKTEST", use_container_width=True, type="primary")

    st.markdown(
        f'<hr style="border-color:{BORDER};margin:20px 0">'
        f'<div style="font-size:10px;color:{MUTED};line-height:1.9">'
        f'<b style="color:{TEXT}">Signal</b><br>12-1 momentum<br>P(t-21) / P(t-252) - 1<br><br>'
        f'<b style="color:{TEXT}">Portfolio</b><br>Equal-weight · Long-only<br>Top-N by momentum rank<br><br>'
        f'<b style="color:{TEXT}">Benchmark</b><br>SPY (S&P 500 ETF)</div>',
        unsafe_allow_html=True,
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="font-family:Rajdhani,sans-serif;font-size:26px;font-weight:700;'
    f'color:{BRIGHT};letter-spacing:3px;margin-bottom:4px;">S&P 500 MOMENTUM STRATEGY</div>'
    f'<div style="font-size:11px;color:{MUTED};margin-bottom:20px;">'
    f'Top 100 Large-Cap &nbsp;·&nbsp; 12-1 Month Signal &nbsp;·&nbsp; Equal-Weight &nbsp;·&nbsp; Long Only</div>',
    unsafe_allow_html=True,
)

# ── Gate ──────────────────────────────────────────────────────────────────────
if not run and "results" not in st.session_state:
    st.markdown(
        f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:12px;'
        f'padding:48px;text-align:center;margin-top:40px">'
        f'<div style="font-size:40px;margin-bottom:16px">📈</div>'
        f'<div style="font-family:Rajdhani,sans-serif;font-size:18px;color:{BRIGHT};'
        f'letter-spacing:2px;margin-bottom:8px">CONFIGURE & RUN</div>'
        f'<div style="color:{MUTED};font-size:12px">Set parameters in the sidebar, then click ▶ RUN BACKTEST</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Run backtest ──────────────────────────────────────────────────────────────
if run:
    prices, benchmark = load_data(period)
    with st.spinner("Running backtest…"):
        port_ret, holdings_hist, rb_log = run_backtest(
            prices, benchmark,
            frequency=frequency, top_n=top_n, lookback=lookback, skip=21,
        )
        metrics = compute_metrics(port_ret, benchmark)
    st.session_state["results"] = dict(
        prices=prices, benchmark=benchmark, port_ret=port_ret,
        holdings_hist=holdings_hist, rb_log=rb_log, metrics=metrics,
        params=dict(frequency=frequency, top_n=top_n, lookback=lookback, period=period),
    )

res           = st.session_state["results"]
prices        = res["prices"]
benchmark     = res["benchmark"]
port_ret      = res["port_ret"]
holdings_hist = res["holdings_hist"]
rb_log        = res["rb_log"]
metrics       = res["metrics"]

# ── KPIs ──────────────────────────────────────────────────────────────────────
section("PERFORMANCE SUMMARY")
c1,c2,c3,c4,c5,c6 = st.columns(6)
with c1: kpi("Total Return",    pct(metrics["total_return"]),     "kpi-green")
with c2: kpi("Ann. Return",     pct(metrics["ann_return"]),       "kpi-green")
with c3: kpi("Sharpe Ratio",    num(metrics["sharpe"]),           "kpi-cyan")
with c4: kpi("Max Drawdown",    pct(metrics["max_drawdown"]),     "kpi-red")
with c5: kpi("Ann. Volatility", pct(metrics["ann_vol"]),          "kpi-amber")
with c6: kpi("Alpha vs SPY",    pct(metrics["alpha"], sign=True), "kpi-purple")
st.markdown("<br>", unsafe_allow_html=True)

# ── Cumulative Performance ────────────────────────────────────────────────────
section("CUMULATIVE PERFORMANCE  ·  STRATEGY vs SPY")
bench_ret = benchmark.pct_change().reindex(port_ret.index).dropna()
port_cum  = (1 + port_ret).cumprod()
bench_cum = (1 + bench_ret).cumprod()

fig_perf = go.Figure()
fig_perf.add_trace(go.Scatter(x=port_cum.index, y=port_cum.values, name="Momentum Strategy",
    line=dict(color=GREEN, width=2), hovertemplate="%{y:.3f}<extra>Strategy</extra>"))
fig_perf.add_trace(go.Scatter(x=bench_cum.index, y=bench_cum.values, name="SPY",
    line=dict(color=CYAN, width=1.5, dash="dot"), hovertemplate="%{y:.3f}<extra>SPY</extra>"))
fig_perf.update_layout(**PLOTLY, height=380, yaxis_tickformat=".2f", yaxis_title="Growth of $1")
st.plotly_chart(fig_perf, use_container_width=True)

# ── Holdings + Scores ─────────────────────────────────────────────────────────
left, right = st.columns([4, 6])

with left:
    section("CURRENT PORTFOLIO HOLDINGS")
    if holdings_hist:
        last_key = max(holdings_hist.keys())
        last     = holdings_hist[last_key]
        wt       = 1.0 / len(last["tickers"])
        df_hold  = pd.DataFrame([
            {"#": i+1, "Ticker": t, "Weight": f"{wt:.1%}",
             "Momentum": f"{last['scores'].get(t, 0):.2%}"}
            for i, t in enumerate(last["tickers"])
        ])
        st.dataframe(df_hold, hide_index=True, use_container_width=True, height=380)
        st.caption(f"As of {last_key}  ·  {len(last['tickers'])} positions  ·  equal-weight")

with right:
    section("MOMENTUM SCORES  ·  CURRENT PORTFOLIO")
    if holdings_hist:
        last_key = max(holdings_hist.keys())
        last     = holdings_hist[last_key]
        tickers  = last["tickers"]
        sc_vals  = [last["scores"].get(t, 0.0) for t in tickers]
        colors   = [GREEN if v >= 0 else RED for v in sc_vals]

        fig_sc = go.Figure(go.Bar(
            x=sc_vals, y=tickers, orientation="h", marker_color=colors,
            text=[f"{v:.1%}" for v in sc_vals], textposition="outside",
            textfont=dict(size=10, color=TEXT),
            hovertemplate="%{y}: %{x:.2%}<extra></extra>",
        ))
        fig_sc.update_layout(
            **PLOTLY, height=380, xaxis_tickformat=".0%", bargap=0.25,
            yaxis=dict(**PLOTLY["yaxis"], autorange="reversed"),
        )
        st.plotly_chart(fig_sc, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Drawdown + Heatmap ────────────────────────────────────────────────────────
dl, dr = st.columns(2)

with dl:
    section("DRAWDOWN")
    cum  = (1 + port_ret).cumprod()
    dd_s = (cum - cum.cummax()) / cum.cummax()
    fig_dd = go.Figure(go.Scatter(
        x=dd_s.index, y=dd_s.values, fill="tozeroy",
        fillcolor="rgba(255,61,113,0.15)", line=dict(color=RED, width=1),
        hovertemplate="%{y:.2%}<extra>Drawdown</extra>",
    ))
    fig_dd.update_layout(**PLOTLY, height=280, yaxis_tickformat=".0%")
    st.plotly_chart(fig_dd, use_container_width=True)

with dr:
    section("MONTHLY RETURNS HEATMAP")
    monthly = port_ret.resample("ME").apply(lambda x: float((1+x).prod()-1))
    mdf = pd.DataFrame({"Year": monthly.index.year, "Month": monthly.index.month, "Ret": monthly.values})
    pivot = mdf.pivot(index="Year", columns="Month", values="Ret")
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    pivot.columns = [month_names[m-1] for m in pivot.columns]

    heat_z    = pivot.values
    heat_text = [[f"{v:.1%}" if not np.isnan(v) else "" for v in row] for row in heat_z]
    fig_heat  = go.Figure(go.Heatmap(
        z=heat_z, x=list(pivot.columns), y=[str(y) for y in pivot.index],
        colorscale=[[0,RED],[0.5,SURFACE],[1,GREEN]], zmid=0,
        text=heat_text, texttemplate="%{text}", textfont=dict(size=10),
        showscale=False, hovertemplate="%{y} %{x}: %{z:.2%}<extra></extra>",
    ))
    fig_heat.update_layout(**PLOTLY, height=280,
                           xaxis=dict(**PLOTLY["xaxis"], side="top"))
    st.plotly_chart(fig_heat, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Rebalancing History ───────────────────────────────────────────────────────
section("REBALANCING HISTORY")
if not rb_log.empty:
    display = rb_log.copy()
    display["Avg Momentum"] = display["Avg Momentum"].map("{:.2%}".format)
    display["Turnover"]     = display["Turnover"].map("{:.0%}".format)
    st.dataframe(display, hide_index=True, use_container_width=True, height=320)
    st.caption(f"{len(rb_log)} rebalances  ·  frequency: {res['params']['frequency']}")
else:
    st.info("No rebalance data.")

# ── Footer ────────────────────────────────────────────────────────────────────
n_stocks = len(prices.columns)
n_days   = len(port_ret)
n_rb     = len(rb_log) if not rb_log.empty else 0
st.markdown(
    f'<div style="margin-top:32px;padding-top:12px;border-top:1px solid {BORDER};'
    f'font-size:10px;color:{MUTED};letter-spacing:1px;">'
    f'UNIVERSE {n_stocks} STOCKS &nbsp;·&nbsp; {n_days} SESSIONS &nbsp;·&nbsp;'
    f'{n_rb} REBALANCES &nbsp;·&nbsp; DATA VIA YAHOO FINANCE &nbsp;·&nbsp; FOR RESEARCH USE ONLY</div>',
    unsafe_allow_html=True,
)
