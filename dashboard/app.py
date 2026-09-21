"""Phase 7 Streamlit monitoring dashboard for the click-fraud Lambda pipeline."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import alerts, load_clicks, load_report


st.set_page_config(page_title="Click Fraud Control Room", page_icon="🛡️", layout="wide")
st.title("Click Fraud Control Room")
st.caption("Speed-layer alerts, delayed-label reconciliation, and drift monitoring")

with st.sidebar:
    st.header("Data sources")
    output_dir = Path(st.text_input("Phase 6 output directory", str(ROOT / "reconciliation" / "output")))
    alert_limit = st.slider("Visible alerts", 10, 500, 100, 10)
    if st.button("Refresh data"):
        st.rerun()
    st.caption("Run `python reconciliation/reconcile.py` to refresh these artifacts.")

report = load_report(output_dir / "reconciliation_metrics.json")
clicks = load_clicks(output_dir / "reconciled_clicks.csv")
if report is None:
    st.info("No Phase 6 output found yet. Run reconciliation, then click Refresh data.")
    st.code("./.venv/bin/python reconciliation/reconcile.py", language="bash")
    st.stop()

speed, batch, latency = report["speed"], report["batch"], report.get("latency_ms", {})
first, second, third, fourth = st.columns(4)
first.metric("Matched clicks", f"{report['matched_clicks']:,}")
second.metric("Layer agreement", f"{report['agreement_rate']:.1%}")
third.metric("Speed PR-AUC", "—" if speed["pr_auc"] is None else f"{speed['pr_auc']:.3f}")
fourth.metric("p99 scoring latency", "—" if not latency else f"{latency['p99']:,.0f} ms")

st.subheader("Drift across replay windows")
drift = report.get("drift_by_replay_window", [])
if drift:
    st.line_chart({
        "speed precision": [window["speed"]["precision"] for window in drift],
        "batch precision": [window["batch"]["precision"] for window in drift],
        "speed recall": [window["speed"]["recall"] for window in drift],
        "batch recall": [window["batch"]["recall"] for window in drift],
    }, x_label="Replay window", y_label="Metric")
    st.caption(f"Batch − speed precision gap in latest window: {drift[-1]['precision_gap_batch_minus_speed']:+.3f}")
else:
    st.warning("The reconciliation report did not contain drift windows.")

left, right = st.columns((1.25, 1))
with left:
    st.subheader("Live / replayed alert feed")
    active_alerts = alerts(clicks, alert_limit)
    if active_alerts.empty:
        st.info("No speed-layer alerts in the joined Phase 6 output.")
    else:
        st.dataframe(active_alerts, use_container_width=True, hide_index=True)
with right:
    st.subheader("Layer comparison")
    st.dataframe({
        "Metric": ["ROC-AUC", "PR-AUC", "Precision", "Recall"],
        "Speed": [speed["roc_auc"], speed["pr_auc"], speed["precision"], speed["recall"]],
        "Batch": [batch["roc_auc"], batch["pr_auc"], batch["precision"], batch["recall"]],
    }, use_container_width=True, hide_index=True)
    st.caption("Accuracy figures use the delayed `is_fraud` label; synthetic click-farm labels are demo-only ground truth.")

chart = output_dir / "reconciliation_charts.png"
if chart.exists():
    st.subheader("Phase 6 analysis bundle")
    st.image(str(chart), use_container_width=True)
