"""Streamlit operator dashboard for live Axon data or explicitly labelled mock data."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
USE_MOCK = os.getenv("USE_MOCK", "0") == "1"
API = os.getenv("BACKEND_URL", f"http://{os.getenv('BACKEND_IP', 'localhost')}:8000")
TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "3"))
REFRESH = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "3"))
st.set_page_config(page_title="AXON | Bearing Intelligence", page_icon="◉", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    :root { --axon-ink: #07111f; --axon-panel: #0d1c2d; --axon-panel-2: #10263a; --axon-line: #29465d; --axon-text: #eaf2f8; --axon-muted: #9eb4c5; --axon-cyan: #41c7c1; --axon-amber: #f7a54b; --axon-red: #ff665f; }
    .stApp { background: radial-gradient(circle at 84% 4%, #173950 0, #091522 34%, #07111f 75%); color: var(--axon-text); }
    .block-container { max-width: 1480px; padding-top: 2rem; padding-bottom: 3.5rem; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #0a1726 0%, #07111f 100%); border-right: 1px solid rgba(158,180,197,.16); }
    [data-testid="stSidebar"] * { color: #dce8f1; }
    h1, h2, h3 { color: var(--axon-text) !important; letter-spacing: -0.025em; }
    .axon-hero { display:flex; justify-content:space-between; align-items:flex-start; gap:24px; margin: 0 0 28px; padding: 30px 34px; border:1px solid rgba(158,180,197,.16); border-radius:22px; background:linear-gradient(125deg, rgba(19,49,70,.96), rgba(11,28,45,.94)); box-shadow:0 18px 48px rgba(0,0,0,.18); }
    .axon-kicker { font-size:.74rem; font-weight:700; letter-spacing:.16em; color:var(--axon-cyan); }
    .axon-hero h1 { margin:.38rem 0 .45rem; font-size:2.35rem; line-height:1.04; }
    .axon-hero p { margin:0; color:var(--axon-muted); max-width:760px; font-size:1rem; }
    .axon-chip { flex:0 0 auto; border:1px solid rgba(65,199,193,.5); border-radius:999px; padding:9px 13px; color:#c9fffb; background:rgba(65,199,193,.10); font-weight:650; font-size:.86rem; }
    .section-label { margin: 18px 0 9px; color:#dce8f1; font-size:1.08rem; font-weight:700; letter-spacing:-.01em; }
    .section-note { color:var(--axon-muted); margin:-3px 0 15px; font-size:.89rem; }
    .diagnostic-card { border:1px solid rgba(158,180,197,.16); border-radius:18px; padding:20px 21px; background:rgba(13,28,45,.78); min-height:115px; }
    .diagnostic-card.alert { border-color:rgba(255,102,95,.62); background:linear-gradient(130deg, rgba(103,32,38,.43), rgba(13,28,45,.9)); }
    .diagnostic-card.good { border-color:rgba(65,199,193,.45); background:linear-gradient(130deg, rgba(25,92,87,.35), rgba(13,28,45,.9)); }
    .diagnostic-eyebrow { color:var(--axon-muted); font-size:.73rem; font-weight:700; letter-spacing:.12em; }
    .diagnostic-value { color:#fff; font-size:1.25rem; line-height:1.25; margin:7px 0 6px; font-weight:720; }
    .diagnostic-detail { color:#c4d4df; font-size:.9rem; line-height:1.45; }
    .part-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; margin-top:10px; }
    .part-card { border:1px solid rgba(158,180,197,.15); border-radius:14px; padding:13px 14px; background:rgba(13,28,45,.65); }
    .part-card.alert { border-left:4px solid var(--axon-red); }
    .part-card.neutral { border-left:4px solid #617b90; }
    .part-title { color:#eef6fb; font-size:.92rem; font-weight:700; }
    .part-status { color:var(--axon-cyan); font-size:.72rem; font-weight:700; letter-spacing:.09em; margin-top:5px; }
    .part-card.alert .part-status { color:#ffaaa5; }
    .part-detail { color:var(--axon-muted); font-size:.8rem; margin-top:5px; line-height:1.32; }
    [data-testid="stMetric"] { background:rgba(13,28,45,.78); border:1px solid rgba(158,180,197,.15); border-radius:14px; padding:14px 16px; }
    [data-testid="stMetricLabel"] { color:var(--axon-muted) !important; }
    [data-testid="stMetricValue"] { color:#f6fbff !important; }
    [data-testid="stFileUploader"] { border:1px dashed rgba(65,199,193,.48); border-radius:16px; padding:8px; background:rgba(13,28,45,.55); }
    .stButton > button { border-radius:10px; border:0; background:linear-gradient(120deg, #35bbb5, #278ea2); color:#041019; font-weight:750; transition:transform .16s ease, filter .16s ease; }
    .stButton > button:hover { transform:translateY(-1px); filter:brightness(1.08); color:#041019; }
    [data-testid="stDataFrame"] { border:1px solid rgba(158,180,197,.15); border-radius:14px; overflow:hidden; }
    [data-testid="stAlert"] { border-radius:12px; }
    @media (max-width: 760px) { .axon-hero { padding:22px; display:block; } .axon-chip { display:inline-block; margin-top:16px; } .part-grid { grid-template-columns:1fr; } }
</style>
""", unsafe_allow_html=True)


def hero(status_text="EDGE MODEL ONLINE"):
    st.markdown(f"""<div class='axon-hero'>
      <div><div class='axon-kicker'>AXON / EDGE DIAGNOSTICS</div><h1>Bearing intelligence, close to the machine</h1>
      <p>Traceable vibration diagnostics with a local model, explicit evidence, and clear service scope.</p></div>
      <div class='axon-chip'>● {status_text}</div>
    </div>""", unsafe_allow_html=True)


def section_title(title, note):
    st.markdown(f"<div class='section-label'>{title}</div><div class='section-note'>{note}</div>", unsafe_allow_html=True)


if USE_MOCK:
    st.warning("MOCK MODE: these readings are generated for UI development, not live machine data.")


def mock(path):
    if path == "/readings":
        return pd.read_csv(Path(__file__).with_name("mock_readings.csv")).to_dict("records")
    if path == "/health": return {"score": 42, "temp_slope": 0.3, "minutes_to_limit": 8.5, "status": "critical"}
    if path == "/alerts": return [{"machine_id": "M1", "ts": "mock", "type": "anomaly", "score": 0.8}]
    return []


def fetch(path, **params):
    if USE_MOCK: return mock(path), None
    try:
        response = requests.get(f"{API}{path}", params=params, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


def issue_command(machine, action):
    try:
        response = requests.post(f"{API}/command", json={"machine_id": machine, "action": action, "issued_by": "dashboard"}, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


def post_json(path, payload):
    try:
        response = requests.post(f"{API}{path}", json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


def bearing_schematic(diagnostic):
    """Highlight the diagnosed drive-end bearing without inventing race-level detail."""
    diagnostic = diagnostic or {}
    location = diagnostic.get("fault_location")
    status = diagnostic.get("status")
    suspected = status in {"FAULT_SUSPECTED", "FAULT_CONFIRMED"}
    confirmed = status == "FAULT_CONFIRMED"
    component = diagnostic.get("component_id", "bearing-drive-end")
    fault_color, neutral = "#dc2626", "#64748b"
    if suspected:
        # The deployed model identifies the drive-end bearing assembly, not a
        # race-level site. Highlight only the service/replace region instead
        # of colouring the internal rings red and implying false precision.
        outer = inner = ball = neutral
        detail = "Service region: drive-end bearing assembly"
    else:
        outer = fault_color if location == "outer_race" else neutral
        inner = fault_color if location == "inner_race" else neutral
        ball = fault_color if location == "rolling_element" else neutral
        detail = "No fault localized" if status else "Awaiting a diagnostic event"
    state = "Technician-confirmed" if confirmed else "Model-predicted / unverified"
    component_color = fault_color if suspected else "#94a3b8"
    service_fill = "#fee2e2" if suspected else "#f8fafc"
    service_label = "INSPECT / REPLACE" if suspected else "BEARING SUPPORT"
    st.markdown(f"""<svg viewBox='0 0 480 210' role='img' aria-label='drive-end bearing component map' style='max-width:520px'>
    <rect x='18' y='66' width='108' height='78' rx='10' fill='#e2e8f0' stroke='#64748b' stroke-width='3'/>
    <text x='72' y='111' text-anchor='middle' fill='#334155' font-size='15'>Motor</text>
    <line x1='126' y1='105' x2='315' y2='105' stroke='#64748b' stroke-width='14' stroke-linecap='round'/>
    <rect x='302' y='42' width='92' height='126' rx='12' fill='{service_fill}' stroke='{component_color}' stroke-width='6'/>
    <path d='M310 70 L386 70 M310 140 L386 140' stroke='{component_color}' stroke-width='3' stroke-dasharray='6 5'/>
    <text x='348' y='188' text-anchor='middle' fill='{component_color}' font-size='13' font-weight='bold'>{service_label}</text>
    <circle cx='430' cy='105' r='66' fill='none' stroke='{outer}' stroke-width='15'/>
    <circle cx='430' cy='105' r='31' fill='none' stroke='{inner}' stroke-width='15'/>
    <circle cx='430' cy='52' r='9' fill='{ball}'/><circle cx='483' cy='105' r='9' fill='{ball}'/><circle cx='430' cy='158' r='9' fill='{ball}'/><circle cx='377' cy='105' r='9' fill='{ball}'/>
    <text x='18' y='204' fill='#475569' font-size='13'>{state}: {component}. {detail}.</text></svg>""", unsafe_allow_html=True)
    if suspected and location is None:
        st.warning("Red marks the drive-end bearing service region only. The deployed model does not make an unsupported inner- or outer-race claim.")
    else:
        st.caption("Red is a model hypothesis, not physical confirmation. Grey means unavailable or unsupported.")


def component_status_table(diagnostic):
    """Translate one diagnostic into an explicit per-part operator view."""
    diagnostic = diagnostic or {}
    status, location = diagnostic.get("status"), diagnostic.get("fault_location")
    suspected = status in {"FAULT_SUSPECTED", "FAULT_CONFIRMED"}
    healthy = status == "HEALTHY_WITHIN_VALIDATED_SCOPE"
    exact_location = {
        "inner_race": "Inner race",
        "outer_race": "Outer race",
        "rolling_element": "Rolling elements",
    }.get(location)
    rows = [
        (
            "Drive-end bearing assembly",
            "FAULT SUSPECTED" if suspected else "HEALTHY WITHIN SCOPE" if healthy else "AWAITING DIAGNOSTIC",
            "Inspect or replace this bearing assembly" if suspected else "No damage detected by the deployed model" if healthy else "Submit a vibration window to assess this component",
            "alert" if suspected else "neutral",
        ),
        (
            "Inner race",
            "SUSPECTED" if exact_location == "Inner race" else "NOT LOCALIZED",
            "Model identified the inner race" if exact_location == "Inner race" else "No validated inner-race conclusion from this diagnostic",
            "alert" if exact_location == "Inner race" else "neutral",
        ),
        (
            "Outer race",
            "SUSPECTED" if exact_location == "Outer race" else "NOT LOCALIZED",
            "Model identified the outer race" if exact_location == "Outer race" else "No validated outer-race conclusion from this diagnostic",
            "alert" if exact_location == "Outer race" else "neutral",
        ),
        (
            "Rolling elements",
            "SUSPECTED" if exact_location == "Rolling elements" else "NOT LOCALIZED",
            "Model identified the rolling elements" if exact_location == "Rolling elements" else "No validated rolling-element conclusion from this diagnostic",
            "alert" if exact_location == "Rolling elements" else "neutral",
        ),
    ]
    cards = "".join(
        f"<div class='part-card {tone}'><div class='part-title'>{part}</div><div class='part-status'>{part_status}</div><div class='part-detail'>{meaning}</div></div>"
        for part, part_status, meaning, tone in rows
    )
    section_title("Part-by-part status", "Red identifies the service region. Subcomponents remain unlocalized unless the model has validated that conclusion.")
    st.markdown(f"<div class='part-grid'>{cards}</div>", unsafe_allow_html=True)


def bearing_diagnosis_panel():
    status, status_error = fetch("/diagnostics/model-status")
    hero("EDGE MODEL ONLINE" if not status_error and status and status.get("available") else "MODEL CHECK REQUIRED")
    section_title("Bearing diagnostic workspace", "Load one vibration window that matches the active model contract. Results remain traceable to the selected asset.")
    input_column, contract_column = st.columns((1.25, .75), gap="large")
    with input_column:
        asset_id = st.text_input("Asset ID", value="demo-motor-001", help="Use a stable equipment identifier for the diagnostic history.")
    with contract_column:
        if status and status.get("available"):
            contract = status["input_contract"]
            st.markdown("<div class='diagnostic-card'><div class='diagnostic-eyebrow'>ACTIVE INPUT CONTRACT</div>"
                        f"<div class='diagnostic-value'>{contract['sampling_frequency_hz']:,.0f} Hz vibration</div>"
                        f"<div class='diagnostic-detail'>{contract['window_samples']:,} samples per window · {len(contract['feature_names'])} engineered features</div></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='diagnostic-card'><div class='diagnostic-eyebrow'>INPUT CONTRACT</div><div class='diagnostic-value'>Unavailable</div><div class='diagnostic-detail'>Deploy a validated bundle before uploading data.</div></div>", unsafe_allow_html=True)
    if status_error:
        st.error(f"Diagnostic API unavailable: {status_error}"); return
    if not status.get("available"):
        st.warning(f"Bearing model unavailable: {status.get('reason', 'no validated bundle is deployed')}")
        st.caption("No bearing fault label, location, cost, or repair instruction is inferred while the model is unavailable.")
    else:
        st.success(f"Active model: {status['model_version']} · {status['kind'].replace('_', ' ')}")
        upload = st.file_uploader("Vibration window CSV", type=["csv"], help="Upload one numeric vibration channel with the exact sample count and frequency shown above.")
        if upload is not None:
            window = pd.read_csv(upload).select_dtypes(include="number")
            if window.empty: st.error("The upload has no numeric vibration column.")
            elif st.button("Run bearing diagnostic", type="primary", use_container_width=True):
                contract = status["input_contract"]
                with st.spinner("Running local edge-model inference..."):
                    result, error = post_json("/diagnostics/infer", {"asset_id": asset_id, "component_id": "bearing-drive-end", "signal": window.iloc[:, 0].tolist(), "sampling_frequency_hz": contract["sampling_frequency_hz"]})
                if error: st.error(error)
                else: st.success(f"Diagnostic record {result['event_id']} created. The view below has been updated.")
    history, history_error = fetch("/diagnostics/history", asset_id=asset_id, limit=20)
    if history_error:
        st.info("No diagnostic history is currently available."); return
    latest = history[0] if history else None
    section_title("Latest diagnostic", "Component localization and the action boundary come directly from the newest saved result.")
    left, right = st.columns((1.18, .82), gap="large")
    with left:
        st.markdown("### Component localization")
        bearing_schematic(latest)
        component_status_table(latest)
    with right:
        st.markdown("### Diagnostic decision")
        if latest:
            suspected = latest.get("status") in {"FAULT_SUSPECTED", "FAULT_CONFIRMED"}
            if suspected:
                st.markdown("<div class='diagnostic-card alert'><div class='diagnostic-eyebrow'>AFFECTED COMPONENT</div><div class='diagnostic-value'>Drive-end bearing assembly</div><div class='diagnostic-detail'>Inspect or replace this bearing assembly. The model does not claim an unvalidated race-level location.</div></div>", unsafe_allow_html=True)
            elif latest.get("status") == "HEALTHY_WITHIN_VALIDATED_SCOPE":
                st.markdown("<div class='diagnostic-card good'><div class='diagnostic-eyebrow'>MODEL DECISION</div><div class='diagnostic-value'>Healthy within validated scope</div><div class='diagnostic-detail'>No bearing damage was detected by this model for the submitted vibration window.</div></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='diagnostic-card'><div class='diagnostic-eyebrow'>MODEL DECISION</div><div class='diagnostic-value'>No actionable localization</div><div class='diagnostic-detail'>The result does not support a component-level service action.</div></div>", unsafe_allow_html=True)
            metric_left, metric_right = st.columns(2)
            metric_left.metric("Confidence", f"{latest.get('confidence', 0):.0%}" if latest.get("confidence") is not None else "Unavailable")
            short_status = {
                "FAULT_SUSPECTED": "Fault",
                "FAULT_CONFIRMED": "Verified",
                "HEALTHY_WITHIN_VALIDATED_SCOPE": "Healthy",
            }.get(latest.get("status"), "Unavailable")
            metric_right.metric("Status", short_status)
            st.markdown(f"**Model class**  \n`{latest.get('fault_class') or 'Unavailable'}`")
            st.markdown(f"**Race-level location**  \n`{latest.get('fault_location') or 'Not localized'}`")
            with st.expander("Technical diagnostic record"):
                st.json({key: latest.get(key) for key in ("asset_id", "component_id", "status", "fault_class", "fault_location", "confidence", "confidence_calibrated", "model_version", "missing_information")})
        else: st.info("No diagnostic has been saved for this asset. Upload a compatible vibration window to begin.")
    with st.expander("Repair intelligence and cost", expanded=False):
        documents, document_error = fetch("/repair-documents/search", query="bearing")
        if document_error or documents.get("status") == "unavailable":
            st.warning("No applicable authorized repair documentation is configured.")
        else: st.dataframe(pd.DataFrame(documents["documents"]), use_container_width=True, hide_index=True)
        st.caption("Prices, compatible parts, and repair procedures remain unavailable until an authorized catalogue and equipment-specific documentation are configured.")
    if history:
        section_title("Diagnostic history", "Each result remains auditable by asset, timestamp, component, model status, and confidence.")
        history_frame = pd.DataFrame(history)
        visible_columns = [column for column in ("timestamp", "status", "component_id", "fault_class", "confidence", "model_version") if column in history_frame]
        st.dataframe(history_frame[visible_columns], use_container_width=True, hide_index=True)


st.sidebar.markdown("### AXON")
st.sidebar.caption("Local edge diagnostics")
view = st.sidebar.radio("Workspace", ("Bearing diagnosis", "Live simulator"))
if view == "Bearing diagnosis":
    st.sidebar.success("Source: Paderborn Bearing DataCenter vibration recordings")
    bearing_diagnosis_panel()
else:
    hero("LIVE TELEMETRY")
    section_title("Machine operations console", "Current telemetry, health trends, alerts, and operator commands from the connected local API.")
    machines, machine_error = fetch("/machines")
    machines = machines or ["M1"]
    machine = st.sidebar.selectbox("Machine", machines)
    if machine_error: st.sidebar.error(f"Backend unavailable: {machine_error}")
    st.sidebar.caption(f"Source: {'mock' if USE_MOCK else API}")
    st.sidebar.caption(f"Refresh interval: {REFRESH}s")

    @st.fragment(run_every=f"{REFRESH}s")
    def live_panel():
        readings, readings_error = fetch("/readings", machine_id=machine, minutes=5)
        health, health_error = fetch("/health", machine_id=machine)
        alerts, alerts_error = fetch("/alerts", machine_id=machine)
        commands, commands_error = fetch("/commands", machine_id=machine)
        if readings_error or health_error or alerts_error or commands_error:
            st.error("Live backend data is unavailable. No mock fallback is used.")
            return
        readings, health, alerts, commands = readings or [], health or {}, alerts or [], commands or []
        df = pd.DataFrame(readings)
        freshness = "absent"
        if not df.empty:
            df["ts"] = pd.to_datetime(df["ts"], utc=True); df = df.sort_values("ts").set_index("ts")
            seconds = (datetime.now(timezone.utc) - df.index[-1].to_pydatetime()).total_seconds()
            freshness = "fresh" if seconds <= REFRESH * 3 else "stale"
        st.caption(f"Telemetry status: {freshness} · Latest reading: {df.index[-1].isoformat() if not df.empty else 'none'}")
        status = health.get("status", "unknown")
        {"healthy": st.success, "warning": st.warning, "critical": st.error}.get(status, st.info)(f"Machine status: {status.upper()}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Health score", health.get("score", "-"))
        c2.metric("Temperature trend", health.get("temp_slope", "-"))
        c3.metric("Minutes to limit", health.get("minutes_to_limit") if health.get("minutes_to_limit") is not None else "-")
        c4.metric("Alerts", len(alerts))
        if df.empty: st.info("No telemetry has arrived for this machine yet.")
        else:
            section_title("Sensor trends", "Temperature, vibration, and current over the most recent telemetry window.")
            st.line_chart(df[["temp", "vibration", "current"]])
        left, right = st.columns(2)
        left.markdown("### Alert feed"); left.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
        right.markdown("### Command history"); right.dataframe(pd.DataFrame(commands), use_container_width=True, hide_index=True)

    live_panel()
    section_title("Operator controls", "Command delivery is confirmed by the broker. Verify equipment execution from edge telemetry or at the machine.")
    st.caption("Publishing a command confirms broker delivery only. Execution must be verified from edge telemetry or the edge terminal.")
    controls = st.columns(3)
    for column, action in zip(controls, ("slow_down", "shutdown", "resume")):
        if action == "shutdown":
            confirm = column.checkbox("Confirm simulated shutdown", key="confirm_shutdown")
            clicked = column.button("Shutdown", disabled=not confirm, type="primary")
        else:
            clicked = column.button(action.replace("_", " ").title())
        if clicked:
            if USE_MOCK: st.info("Mock mode does not send commands.")
            else:
                result, error = issue_command(machine, action)
                if error: st.error(f"Command not published: {error}")
                else: st.success(f"{action} command {result['status']}; verify execution at the edge.")
