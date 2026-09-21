"""Phase 8 Click Fraud Control Room — full monitoring dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import (
    alerts,
    campaign_fraud_rates,
    load_batch_scored,
    load_clicks,
    load_report,
    publisher_fraud_rates,
)

# ---------------------------------------------------------------------------
# Page config & custom CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Click Fraud Control Room",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* ── Global dark-navy base ── */
    html, body, [data-testid="stAppViewContainer"] {
        background: #0d1117;
        color: #e6edf3;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    [data-testid="stSidebar"] {
        background: #161b22;
        border-right: 1px solid #21262d;
    }
    /* ── KPI card metric ── */
    [data-testid="stMetric"] {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 10px;
        padding: 16px 20px;
    }
    [data-testid="stMetricLabel"] > div {
        color: #8b949e;
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    [data-testid="stMetricValue"] > div {
        color: #f0f6fc;
        font-size: 1.9rem;
        font-weight: 700;
        font-family: 'Courier New', monospace;
    }
    /* ── Tab strip ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #161b22;
        border-radius: 8px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 6px;
        color: #8b949e;
        font-size: 0.85rem;
        font-weight: 500;
        padding: 6px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: #21262d !important;
        color: #f0f6fc !important;
    }
    /* ── Section headers ── */
    h2, h3 { color: #f0f6fc; font-weight: 600; }
    /* ── Amber accent banner ── */
    .alert-banner {
        background: linear-gradient(90deg, #b45309 0%, #92400e 100%);
        border-radius: 8px;
        padding: 10px 18px;
        margin-bottom: 12px;
        font-size: 0.9rem;
        color: #fef3c7;
        font-weight: 500;
    }
    /* ── Subtle divider ── */
    hr { border-color: #21262d; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🛡️ Click Fraud\n**Control Room**")
    st.divider()
    st.subheader("Data sources")
    output_dir = Path(
        st.text_input("Phase 6 output directory", str(ROOT / "reconciliation" / "output"))
    )
    batch_parquet = Path(
        st.text_input("Batch scored parquet", str(ROOT / "data" / "batch" / "batch_scored_clicks.parquet"))
    )
    alert_limit = st.slider("Max alert rows", 10, 500, 150, 10)
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("Phase 8 — Ad-Click Fraud Detection\nLambda Architecture · Kafka · Flink · Spark")

# ---------------------------------------------------------------------------
# Load data (cached for performance)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load_report(p: str):
    return load_report(Path(p))

@st.cache_data(ttl=60)
def _load_clicks(p: str):
    return load_clicks(Path(p))

@st.cache_data(ttl=300)
def _load_batch(p: str):
    return load_batch_scored(Path(p))

report = _load_report(str(output_dir / "reconciliation_metrics.json"))
clicks = _load_clicks(str(output_dir / "reconciled_clicks.csv"))
batch_df = _load_batch(str(batch_parquet))

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    "<h1 style='margin-bottom:4px;color:#f0f6fc;'>🛡️ Click Fraud Control Room</h1>"
    "<p style='color:#8b949e;margin-top:0;'>Speed-layer alerts · Campaign/publisher intelligence · Drift monitoring</p>",
    unsafe_allow_html=True,
)

if report is None:
    st.info("No Phase 6 output found yet. Run reconciliation, then click **Refresh data**.")
    st.code("./.venv/bin/python reconciliation/reconcile.py", language="bash")
    st.stop()

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

speed, batch_m, latency = report["speed"], report["batch"], report.get("latency_ms", {})
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Matched clicks", f"{report['matched_clicks']:,}")
c2.metric("Layer agreement", f"{report['agreement_rate']:.1%}")
c3.metric("Speed PR-AUC", "—" if speed["pr_auc"] is None else f"{speed['pr_auc']:.4f}")
c4.metric("Batch PR-AUC", "—" if batch_m["pr_auc"] is None else f"{batch_m['pr_auc']:.4f}")
c5.metric("p99 latency", "—" if not latency else f"{latency['p99']:,.0f} ms")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_campaign, tab_publisher, tab_drift, tab_alerts, tab_charts = st.tabs([
    "📊 Campaign View",
    "🏢 Publisher View",
    "📉 Drift & Accuracy",
    "🚨 Alert Feed",
    "🖼️ Phase 6 Charts",
])

# ── Plotly theme shared across charts ──────────────────────────────────────
# PX_THEME  → valid as keyword args to px.bar / px.scatter / px.histogram
# LAYOUT_THEME → go into update_layout() / go.Figure layout
PX_THEME = dict(template="plotly_dark")
LAYOUT_THEME = dict(paper_bgcolor="#0d1117", plot_bgcolor="#0d1117")

# ── Tab 1: Campaign View ────────────────────────────────────────────────────
with tab_campaign:
    if batch_df.empty:
        st.warning("Batch parquet not found. Check sidebar path.")
    else:
        camp = campaign_fraud_rates(batch_df)
        top_n = st.slider("Top N campaigns", 10, min(100, len(camp)), 30, key="camp_slider")
        camp_top = camp.head(top_n).copy()
        camp_top["campaign_id"] = camp_top["campaign_id"].astype(str)

        col_left, col_right = st.columns((2, 1))
        with col_left:
            st.markdown("#### Flag Rate by Campaign")
            fig = px.bar(
                camp_top,
                x="campaign_id",
                y="flag_rate",
                color="flag_rate",
                color_continuous_scale=["#1e3a5f", "#f59e0b", "#dc2626"],
                labels={"campaign_id": "Campaign ID", "flag_rate": "Flag Rate"},
                hover_data={"total_clicks": True, "flagged": True, "fraud_rate": ":.3f"},
                **PX_THEME,
            )
            fig.update_layout(
                coloraxis_showscale=False,
                xaxis=dict(tickangle=-45, title_font_color="#8b949e"),
                yaxis=dict(tickformat=".0%", title_font_color="#8b949e"),
                height=380,
                margin=dict(l=10, r=10, t=30, b=60),
                **LAYOUT_THEME,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.markdown("#### Top Flagged Campaigns")
            display_cols = {"campaign_id": "Campaign", "total_clicks": "Clicks",
                            "flagged": "Flagged", "flag_rate": "Flag Rate",
                            "confirmed_fraud": "Fraud"}
            st.dataframe(
                camp_top[list(display_cols.keys())].rename(columns=display_cols)
                .style.format({"Flag Rate": "{:.2%}"})
                .background_gradient(subset=["Flag Rate"], cmap="YlOrRd"),
                use_container_width=True,
                hide_index=True,
                height=380,
            )

        st.divider()
        st.markdown("#### Fraud Confirmed vs Flagged (Top 30 Campaigns)")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=camp_top["campaign_id"].astype(str),
            y=camp_top["flagged"],
            name="Flagged by model",
            marker_color="#f59e0b",
        ))
        fig2.add_trace(go.Bar(
            x=camp_top["campaign_id"].astype(str),
            y=camp_top["confirmed_fraud"],
            name="Confirmed fraud",
            marker_color="#dc2626",
        ))
        fig2.update_layout(
            barmode="overlay",
            xaxis_tickangle=-45,
            height=320,
            margin=dict(l=10, r=10, t=10, b=60),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            **PX_THEME,
            **LAYOUT_THEME,
        )
        st.plotly_chart(fig2, use_container_width=True)

# ── Tab 2: Publisher View ───────────────────────────────────────────────────
with tab_publisher:
    if batch_df.empty:
        st.warning("Batch parquet not found. Check sidebar path.")
    else:
        pub = publisher_fraud_rates(batch_df)
        top_n_p = st.slider("Top N publishers", 10, min(100, len(pub)), 30, key="pub_slider")
        pub_top = pub.head(top_n_p).copy()
        pub_top["publisher_id"] = pub_top["publisher_id"].astype(str)

        col_left, col_right = st.columns((2, 1))
        with col_left:
            st.markdown("#### Flag Rate by Publisher")
            fig = px.bar(
                pub_top,
                x="publisher_id",
                y="flag_rate",
                color="flag_rate",
                color_continuous_scale=["#1e3a5f", "#a855f7", "#dc2626"],
                labels={"publisher_id": "Publisher ID", "flag_rate": "Flag Rate"},
                hover_data={"total_clicks": True, "flagged": True, "fraud_rate": ":.3f"},
                **PX_THEME,
            )
            fig.update_layout(
                coloraxis_showscale=False,
                xaxis=dict(tickangle=-45, title_font_color="#8b949e"),
                yaxis=dict(tickformat=".0%", title_font_color="#8b949e"),
                height=380,
                margin=dict(l=10, r=10, t=30, b=60),
                **LAYOUT_THEME,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.markdown("#### Top Flagged Publishers")
            display_cols = {"publisher_id": "Publisher", "total_clicks": "Clicks",
                            "flagged": "Flagged", "flag_rate": "Flag Rate",
                            "confirmed_fraud": "Fraud"}
            st.dataframe(
                pub_top[list(display_cols.keys())].rename(columns=display_cols)
                .style.format({"Flag Rate": "{:.2%}"})
                .background_gradient(subset=["Flag Rate"], cmap="PuRd"),
                use_container_width=True,
                hide_index=True,
                height=380,
            )

        st.divider()
        st.markdown("#### Mean Fraud Score Distribution Across Publishers")
        fig3 = px.scatter(
            pub,
            x="total_clicks",
            y="flag_rate",
            size="flagged",
            color="confirmed_fraud",
            color_continuous_scale=["#1e3a5f", "#a855f7", "#dc2626"],
            hover_data=["publisher_id"],
            labels={
                "total_clicks": "Total Clicks",
                "flag_rate": "Flag Rate",
                "confirmed_fraud": "Confirmed Fraud",
            },
            **PX_THEME,
        )
        fig3.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=10, b=40),
            **LAYOUT_THEME,
        )
        st.plotly_chart(fig3, use_container_width=True)

# ── Tab 3: Drift & Accuracy ─────────────────────────────────────────────────
with tab_drift:
    drift = report.get("drift_by_replay_window", [])
    if not drift:
        st.warning("The reconciliation report does not contain drift windows.")
    else:
        windows = [w["window"] for w in drift]
        speed_prec = [w["speed"]["precision"] for w in drift]
        batch_prec = [w["batch"]["precision"] for w in drift]
        speed_rec = [w["speed"]["recall"] for w in drift]
        batch_rec = [w["batch"]["recall"] for w in drift]
        gap = [w["precision_gap_batch_minus_speed"] for w in drift]

        fig_drift = go.Figure()
        fig_drift.add_trace(go.Scatter(x=windows, y=speed_prec, mode="lines+markers",
                                       name="Speed precision", line=dict(color="#f59e0b", width=2)))
        fig_drift.add_trace(go.Scatter(x=windows, y=batch_prec, mode="lines+markers",
                                       name="Batch precision", line=dict(color="#3b82f6", width=2)))
        fig_drift.add_trace(go.Scatter(x=windows, y=speed_rec, mode="lines+markers",
                                       name="Speed recall", line=dict(color="#f59e0b", width=2, dash="dot")))
        fig_drift.add_trace(go.Scatter(x=windows, y=batch_rec, mode="lines+markers",
                                       name="Batch recall", line=dict(color="#3b82f6", width=2, dash="dot")))
        fig_drift.update_layout(
            title="Precision & Recall across Replay Windows",
            xaxis_title="Replay window",
            yaxis_title="Score",
            yaxis=dict(range=[0, 1.05]),
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            **PX_THEME,
            **LAYOUT_THEME,
        )
        st.plotly_chart(fig_drift, use_container_width=True)

        col_a, col_b = st.columns((1, 1))
        with col_a:
            st.markdown(f"**Batch − Speed precision gap (latest window):** "
                        f"`{gap[-1]:+.3f}`")
            st.caption(
                "Positive gap means batch layer catches more fraud than the speed layer "
                "in that replay slice — the penalty for not yet having retraining data."
            )

        with col_b:
            st.markdown("#### Speed vs Batch — Overall")
            st.dataframe(
                {
                    "Metric": ["ROC-AUC", "PR-AUC", "Precision", "Recall"],
                    "Speed layer": [
                        speed["roc_auc"], speed["pr_auc"],
                        speed["precision"], speed["recall"],
                    ],
                    "Batch layer": [
                        batch_m["roc_auc"], batch_m["pr_auc"],
                        batch_m["precision"], batch_m["recall"],
                    ],
                },
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Accuracy uses delayed `is_fraud` labels; synthetic click-farm "
                "labels are demo ground truth only."
            )

        # Latency sub-section
        if latency:
            st.divider()
            st.markdown("#### Speed-Layer Scoring Latency")
            l_cols = st.columns(3)
            l_cols[0].metric("p50", f"{latency['p50']:,.0f} ms")
            l_cols[1].metric("p95", f"{latency['p95']:,.0f} ms")
            l_cols[2].metric("p99", f"{latency['p99']:,.0f} ms")
            st.caption(
                "Latency = Kafka publish → Flink consume → feature compute → XGBoost inference. "
                "p99 plateau near p95 indicates steady-state backpressure under single-partition load, "
                "not unbounded queue growth."
            )

# ── Tab 4: Alert Feed ───────────────────────────────────────────────────────
with tab_alerts:
    active = alerts(clicks, alert_limit)
    if active.empty:
        st.info("No speed-layer alerts in the Phase 6 reconciled output.")
    else:
        n_alerts = len(clicks[clicks["speed_flagged"].fillna(0).astype(int) == 1]) if not clicks.empty else 0
        st.markdown(
            f'<div class="alert-banner">⚠️ {n_alerts:,} speed-layer alerts in replay window '
            f'— showing newest {min(alert_limit, n_alerts)}</div>',
            unsafe_allow_html=True,
        )
        prob_cols = ["speed_probability", "batch_probability"]
        show = active.copy()
        for c in prob_cols:
            if c in show:
                show[c] = show[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "—")
        if "latency_ms" in show:
            show["latency_ms"] = show["latency_ms"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
        st.dataframe(show, use_container_width=True, hide_index=True)

        # Small latency distribution if available
        if not clicks.empty and "latency_ms" in clicks:
            lat_data = clicks["latency_ms"].dropna()
            if len(lat_data) > 0:
                st.divider()
                st.markdown("#### End-to-End Scoring Latency Distribution")
                fig_lat = px.histogram(
                    lat_data,
                    nbins=50,
                    labels={"value": "Latency (ms)", "count": "Clicks"},
                    color_discrete_sequence=["#f59e0b"],
                    **PX_THEME,
                )
                fig_lat.update_layout(
                    height=260,
                    margin=dict(l=10, r=10, t=10, b=40),
                    showlegend=False,
                    **LAYOUT_THEME,
                )
                st.plotly_chart(fig_lat, use_container_width=True)

# ── Tab 5: Phase 6 Charts ───────────────────────────────────────────────────
with tab_charts:
    chart_path = output_dir / "reconciliation_charts.png"
    if chart_path.exists():
        st.markdown("#### Phase 6 Reconciliation Analysis Bundle")
        st.caption(
            "Score distributions · Precision–recall curves · "
            "Precision drift across replay windows · Alerts vs confirmations"
        )
        st.image(str(chart_path), use_container_width=True)
    else:
        st.warning(f"Chart bundle not found at `{chart_path}`. Run reconciliation first.")
        st.code("./.venv/bin/python reconciliation/reconcile.py", language="bash")
