"""
momentum_strategy_v02.py  —  S&P 500 Momentum Strategy  ·  Light Theme Dashboard
──────────────────────────────────────────────────────────────────────────────────
Run with:
    streamlit run momentum_strategy_v02.py
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

# ── Design tokens — light theme ───────────────────────────────────────────────
BG      = "#F8FAFC"
SURFACE = "#FFFFFF"
CARD    = "#FFFFFF"
BORDER  = "#E2E8F0"

GREEN   = "#16A34A"
RED     = "#DC2626"
BLUE    = "#2563EB"
AMBER   = "#D97706"
PURPLE  = "#7C3AED"
TEAL    = "#0891B2"
MUTED   = "#64748B"
TEXT    = "#1E293B"
BRIGHT  = "#0F172A"

PLOTLY = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family="'Inter', sans-serif", size=11),
    margin=dict(l=12, r=12, t=28, b=12),
    hovermode="x unified",
    hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER, font_color=BRIGHT),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
    xaxis=dict(gridcolor=BORDER, gridwidth=0.6, linecolor=BORDER, zeroline=False),
    yaxis=dict(gridcolor=BORDER, gridwidth=0.6, linecolor=BORDER, zeroline=False),
)

# ── Global CSS ────────────────────────────────────────────────────────────────
# Fonts: Inter (clean Latin UI font) + JetBrains Mono (numeric values).
# Rajdhani is excluded — it carries Devanagari glyphs that render non-English
# characters on some systems.
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [data-testid="stAppViewContainer"] {{
    background: {BG};
    color: {TEXT};
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}}
[data-testid="stSidebar"] {{
    background: {SURFACE} !important;
    border-right: 1px solid {BORDER};
}}
[data-testid="stSidebar"] * {{ color: {TEXT} !important; }}
.block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}

/* Streamlit widget text */
.stSelectbox label, .stSlider label, .stButton button {{
    font-family: 'Inter', sans-serif !important;
    color: {TEXT} !important;
}}
.stButton > button {{
    background: {BLUE} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
}}
.stButton > button:hover {{
    background: #1D4ED8 !important;
}}

/* KPI cards */
.kpi-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 16px 20px;
    height: 90px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}
.kpi-label {{
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: {MUTED};
    margin-bottom: 6px;
}}
.kpi-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 600;
    line-height: 1;
}}
.kpi-green  {{ color: {GREEN}; }}
.kpi-red    {{ color: {RED}; }}
.kpi-blue   {{ color: {BLUE}; }}
.kpi-amber  {{ color: {AMBER}; }}
.kpi-purple {{ color: {PURPLE}; }}

/* Section headers */
.section-hdr {{
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: {MUTED};
    border-bottom: 1px solid {BORDER};
    padding-bottom: 6px;
    margin-bottom: 10px;
}}

/* App header */
.app-title {{
    font-family: 'Inter', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: {BRIGHT};
    letter-spacing: -0.5px;
    margin-bottom: 2px;
}}
.app-subtitle {{
    font-size: 12px;
    color: {MUTED};
    margin-bottom: 20px;
}}

/* Sidebar branding */
.sidebar-brand {{
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    font-weight: 700;
    color: {BRIGHT};
    letter-spacing: 0px;
    margin-bottom: 2px;
}}
.sidebar-sub {{
    font-size: 10px;
    color: {MUTED};
    letter-spacing: 0.5px;
    margin-bottom: 20px;
}}

#MainMenu, footer, header {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def kpi(label: str, value: str, color_cls: str = "kpi-blue") -> None:
    st.markdown(
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value {color_cls}">{value}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f'<div class="section-hdr">{title}</div>', unsafe_allow_html=True)


def pct(v, sign: bool = False) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{'+' if sign and v > 0 else ''}{v:.1%}"


def num(v, d: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.{d}f}"


@st.cache_data(show_spinner="Downloading price data from Yahoo Finance...")
def load_data(period: str):
    return fetch_data(UNIVERSE, period=period)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand">Momentum</div>'
        f'<div class="sidebar-sub">S&P 500 · Top 100 Large-Cap</div>',
        unsafe_allow_html=True,
    )

    frequency = st.selectbox(
        "Rebalancing Frequency",
        options=["monthly", "biweekly"],
        format_func=lambda x: "Monthly (last trading day)" if x == "monthly"
                              else "Biweekly (~10 sessions)",
    )
    lookback = st.selectbox(
        "Momentum Lookback",
        options=[126, 189, 252],
        index=2,
        format_func=lambda x: {126: "6 Months", 189: "9 Months", 252: "12 Months"}[x],
    )
    top_n = st.slider("Portfolio Size (Top-N)", min_value=10, max_value=40, step=5, value=20)
    period = st.selectbox(
        "Historical Period",
        options=["2y", "3y", "5y"],
        index=0,
        format_func=lambda x: {"2y": "2 Years", "3y": "3 Years", "5y": "5 Years"}[x],
    )

    st.markdown("<br>", unsafe_allow_html=True)
    run = st.button("Run Backtest", use_container_width=True, type="primary")

    st.markdown(
        f'<hr style="border-color:{BORDER};margin:20px 0">'
        f'<div style="font-size:11px;color:{MUTED};line-height:1.9;font-family:Inter,sans-serif">'
        f'<b style="color:{TEXT}">Signal</b><br>'
        f'12-1 momentum<br>'
        f'P(t-21) / P(t-252) - 1<br><br>'
        f'<b style="color:{TEXT}">Portfolio</b><br>'
        f'Equal-weight · Long-only<br>'
        f'Top-N by momentum rank<br><br>'
        f'<b style="color:{TEXT}">Benchmark</b><br>'
        f'SPY (S&P 500 ETF)</div>',
        unsafe_allow_html=True,
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="app-title">S&P 500 Momentum Strategy</div>'
    '<div class="app-subtitle">'
    'Top 100 Large-Cap &nbsp;&middot;&nbsp; 12-1 Month Signal '
    '&nbsp;&middot;&nbsp; Equal-Weight &nbsp;&middot;&nbsp; Long Only'
    '</div>',
    unsafe_allow_html=True,
)

#st.subheader("Developed by: Al Yazdani",divider=True)  # add spacing after header for better aesthetics
st.markdown("Developed by: Al Yazdani")


# ── Gate ──────────────────────────────────────────────────────────────────────
if not run and "results_v2" not in st.session_state:
    st.markdown(
        f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:12px;'
        f'padding:56px;text-align:center;margin-top:40px;'
        f'box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
        f'<div style="font-size:44px;margin-bottom:16px">📈</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:18px;font-weight:700;'
        f'color:{BRIGHT};margin-bottom:8px">Configure &amp; Run</div>'
        f'<div style="color:{MUTED};font-size:13px">'
        f'Set parameters in the sidebar, then click <b>Run Backtest</b></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Run backtest ──────────────────────────────────────────────────────────────
if run:
    prices, benchmark = load_data(period)
    with st.spinner("Running backtest..."):
        port_ret, holdings_hist, rb_log = run_backtest(
            prices, benchmark,
            frequency=frequency, top_n=top_n, lookback=lookback, skip=21,
        )
        metrics = compute_metrics(port_ret, benchmark)
    st.session_state["results_v2"] = dict(
        prices=prices, benchmark=benchmark, port_ret=port_ret,
        holdings_hist=holdings_hist, rb_log=rb_log, metrics=metrics,
        params=dict(frequency=frequency, top_n=top_n, lookback=lookback, period=period),
    )

res           = st.session_state["results_v2"]
prices        = res["prices"]
benchmark     = res["benchmark"]
port_ret      = res["port_ret"]
holdings_hist = res["holdings_hist"]
rb_log        = res["rb_log"]
metrics       = res["metrics"]

# ── KPIs ──────────────────────────────────────────────────────────────────────
section("Performance Summary")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: kpi("Total Return",    pct(metrics["total_return"]),     "kpi-green")
with c2: kpi("Ann. Return",     pct(metrics["ann_return"]),       "kpi-green")
with c3: kpi("Sharpe Ratio",    num(metrics["sharpe"]),           "kpi-blue")
with c4: kpi("Max Drawdown",    pct(metrics["max_drawdown"]),     "kpi-red")
with c5: kpi("Ann. Volatility", pct(metrics["ann_vol"]),          "kpi-amber")
with c6: kpi("Alpha vs SPY",    pct(metrics["alpha"], sign=True), "kpi-purple")
st.markdown("<br>", unsafe_allow_html=True)

# ── Cumulative Performance ────────────────────────────────────────────────────
section("Cumulative Performance  ·  Strategy vs SPY")
bench_ret = benchmark.pct_change().reindex(port_ret.index).dropna()
port_cum  = (1 + port_ret).cumprod()
bench_cum = (1 + bench_ret).cumprod()

fig_perf = go.Figure()
fig_perf.add_trace(go.Scatter(
    x=port_cum.index, y=port_cum.values, name="Momentum Strategy",
    line=dict(color=GREEN, width=2.5),
    hovertemplate="%{y:.3f}<extra>Strategy</extra>",
))
fig_perf.add_trace(go.Scatter(
    x=bench_cum.index, y=bench_cum.values, name="SPY",
    line=dict(color=BLUE, width=1.8, dash="dot"),
    hovertemplate="%{y:.3f}<extra>SPY</extra>",
))
fig_perf.update_layout(
    **PLOTLY, height=380,
    yaxis_tickformat=".2f",
    yaxis_title="Growth of $1",
)
st.plotly_chart(fig_perf, use_container_width=True)

# ── Holdings + Scores ─────────────────────────────────────────────────────────
left, right = st.columns([4, 6])

with left:
    section("Current Portfolio Holdings")
    if holdings_hist:
        last_key = max(holdings_hist.keys())
        last     = holdings_hist[last_key]
        wt       = 1.0 / len(last["tickers"])
        df_hold  = pd.DataFrame([
            {
                "#":        i + 1,
                "Ticker":   t,
                "Weight":   f"{wt:.1%}",
                "Momentum": f"{last['scores'].get(t, 0):.2%}",
            }
            for i, t in enumerate(last["tickers"])
        ])
        st.dataframe(df_hold, hide_index=True, use_container_width=True, height=380)
        st.caption(f"As of {last_key}  ·  {len(last['tickers'])} positions  ·  equal-weight")

with right:
    section("Momentum Scores  ·  Current Portfolio")
    if holdings_hist:
        last_key = max(holdings_hist.keys())
        last     = holdings_hist[last_key]
        tickers  = last["tickers"]
        sc_vals  = [last["scores"].get(t, 0.0) for t in tickers]
        bar_colors = [GREEN if v >= 0 else RED for v in sc_vals]

        fig_sc = go.Figure(go.Bar(
            x=sc_vals, y=tickers, orientation="h",
            marker_color=bar_colors,
            text=[f"{v:.1%}" for v in sc_vals],
            textposition="outside",
            textfont=dict(size=10, color=TEXT),
            hovertemplate="%{y}: %{x:.2%}<extra></extra>",
        ))
        _sc_layout = {k: v for k, v in PLOTLY.items() if k != "yaxis"}
        fig_sc.update_layout(
            **_sc_layout, height=380,
            xaxis_tickformat=".0%",
            bargap=0.25,
            yaxis=dict(**PLOTLY["yaxis"], autorange="reversed"),
        )
        st.plotly_chart(fig_sc, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Drawdown + Heatmap ────────────────────────────────────────────────────────
dl, dr = st.columns(2)

with dl:
    section("Drawdown")
    cum  = (1 + port_ret).cumprod()
    dd_s = (cum - cum.cummax()) / cum.cummax()
    fig_dd = go.Figure(go.Scatter(
        x=dd_s.index, y=dd_s.values,
        fill="tozeroy",
        fillcolor="rgba(220,38,38,0.10)",
        line=dict(color=RED, width=1.5),
        hovertemplate="%{y:.2%}<extra>Drawdown</extra>",
    ))
    fig_dd.update_layout(**PLOTLY, height=280, yaxis_tickformat=".0%")
    st.plotly_chart(fig_dd, use_container_width=True)

with dr:
    section("Monthly Returns Heatmap")
    monthly = port_ret.resample("ME").apply(lambda x: float((1 + x).prod() - 1))
    mdf     = pd.DataFrame({
        "Year":  monthly.index.year,
        "Month": monthly.index.month,
        "Ret":   monthly.values,
    })
    pivot = mdf.pivot(index="Year", columns="Month", values="Ret")
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    pivot.columns = [month_names[m - 1] for m in pivot.columns]

    heat_z    = pivot.values
    heat_text = [[f"{v:.1%}" if not np.isnan(v) else "" for v in row] for row in heat_z]
    fig_heat  = go.Figure(go.Heatmap(
        z=heat_z,
        x=list(pivot.columns),
        y=[str(y) for y in pivot.index],
        colorscale=[[0, RED], [0.5, "#F1F5F9"], [1, GREEN]],
        zmid=0,
        text=heat_text,
        texttemplate="%{text}",
        textfont=dict(size=10),
        showscale=False,
        hovertemplate="%{y} %{x}: %{z:.2%}<extra></extra>",
    ))
    _heat_layout = {k: v for k, v in PLOTLY.items() if k != "xaxis"}
    fig_heat.update_layout(
        **_heat_layout, height=280,
        xaxis=dict(**PLOTLY["xaxis"], side="top"),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Rebalancing History ───────────────────────────────────────────────────────
section("Rebalancing History")
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
    f'font-size:11px;color:{MUTED};font-family:Inter,sans-serif;">'
    f'Universe: {n_stocks} stocks &nbsp;&middot;&nbsp; {n_days} sessions '
    f'&nbsp;&middot;&nbsp; {n_rb} rebalances '
    f'&nbsp;&middot;&nbsp; Data via Yahoo Finance '
    f'&nbsp;&middot;&nbsp; For research use only'
    f'</div>',
    unsafe_allow_html=True,
)
