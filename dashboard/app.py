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
    :root { --axon-ink: #17212b; --axon-panel: #ffffff; --axon-panel-2: #f8fafc; --axon-line: #d9e1e8; --axon-text: #17212b; --axon-muted: #667788; --axon-cyan: #0f766e; --axon-amber: #b45309; --axon-red: #b42318; }
    .stApp { background: #f6f8fa; color: var(--axon-text); }
    .block-container { max-width: 1480px; padding-top: 1.5rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #dfe6ec; }
    [data-testid="stSidebar"] * { color: #273543; }
    h1, h2, h3 { color: var(--axon-text) !important; letter-spacing: -0.025em; }
    .axon-hero { display:flex; justify-content:space-between; align-items:flex-start; gap:24px; margin: 0 0 24px; padding: 26px 28px; border:1px solid #d9e1e8; border-radius:4px; background:#ffffff; }
    .axon-kicker { font-size:.72rem; font-weight:700; letter-spacing:.1em; color:var(--axon-cyan); }
    .axon-hero h1 { margin:.35rem 0 .4rem; font-size:2.15rem; line-height:1.1; }
    .axon-hero p { margin:0; color:var(--axon-muted); max-width:760px; font-size:1rem; }
    .axon-chip { flex:0 0 auto; border:1px solid #9bd6cc; border-radius:3px; padding:8px 11px; color:#0f5d56; background:#edf9f6; font-weight:700; font-size:.78rem; }
    .section-label { margin: 18px 0 9px; color:var(--axon-text); font-size:1.08rem; font-weight:700; letter-spacing:-.01em; }
    .section-note { color:var(--axon-muted); margin:-3px 0 15px; font-size:.89rem; }
    .diagnostic-card { border:1px solid #d9e1e8; border-radius:4px; padding:19px 20px; background:#ffffff; min-height:115px; }
    .diagnostic-card.alert { border-color:#e4b2ad; background:#fffafa; }
    .diagnostic-card.good { border-color:#a9d8d0; background:#f7fcfb; }
    .diagnostic-eyebrow { color:var(--axon-muted); font-size:.73rem; font-weight:700; letter-spacing:.12em; }
    .diagnostic-value { color:var(--axon-text); font-size:1.25rem; line-height:1.25; margin:7px 0 6px; font-weight:720; }
    .diagnostic-detail { color:#526475; font-size:.9rem; line-height:1.45; }
    .stream-card { display:flex; align-items:center; gap:16px; padding:15px 17px; margin:0 0 18px; border:1px solid #d9e1e8; border-radius:4px; background:#ffffff; }
    .stream-indicator { flex:0 0 auto; width:10px; height:10px; border-radius:50%; background:#0f766e; box-shadow:0 0 0 4px #d9f2ed; }
    .stream-indicator.waiting { background:#b45309; box-shadow:0 0 0 4px #fdf0d8; }
    .stream-copy { min-width:0; }
    .stream-title { color:var(--axon-text); font-size:.91rem; font-weight:700; }
    .stream-detail { color:var(--axon-muted); margin-top:2px; font-size:.82rem; line-height:1.35; }
    .stream-meta { margin-left:auto; color:#526475; font-size:.78rem; text-align:right; white-space:nowrap; }
    .bearing-stage { margin:4px 0 2px; padding:14px 16px 10px; border:1px solid #d9e1e8; border-radius:4px; background:#ffffff; }
    .bearing-stage-title { color:#526475; font-size:.72rem; font-weight:700; letter-spacing:.1em; }
    .bearing-stage svg { display:block; width:100%; max-width:650px; height:auto; margin:3px auto 0; }
    .bearing-stage-note { color:var(--axon-muted); font-size:.81rem; line-height:1.4; }
    .part-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; margin-top:10px; }
    .part-card { border:1px solid #d9e1e8; border-radius:4px; padding:13px 14px; background:#ffffff; }
    .part-card.alert { border-color:#dfaaa5; background:#fffafa; }
    .part-card.neutral { border-color:#d9e1e8; }
    .part-title { color:var(--axon-text); font-size:.92rem; font-weight:700; }
    .part-status { color:var(--axon-cyan); font-size:.72rem; font-weight:700; letter-spacing:.06em; margin-top:5px; }
    .part-card.alert .part-status { color:var(--axon-red); }
    .part-detail { color:var(--axon-muted); font-size:.8rem; margin-top:5px; line-height:1.32; }
    [data-testid="stMetric"] { background:#ffffff; border:1px solid #d9e1e8; border-radius:4px; padding:14px 16px; }
    [data-testid="stMetricLabel"] { color:var(--axon-muted) !important; }
    [data-testid="stMetricValue"] { color:var(--axon-text) !important; }
    [data-testid="stFileUploader"] { border:1px dashed #b8c5d0; border-radius:4px; padding:8px; background:#ffffff; }
    .stButton > button { border-radius:4px; border:1px solid #0f766e; background:#0f766e; color:#ffffff; font-weight:700; transition:background-color .16s ease; }
    .stButton > button:hover { background:#0b625b; color:#ffffff; }
    [data-testid="stDataFrame"] { border:1px solid #d9e1e8; border-radius:4px; overflow:hidden; }
    [data-testid="stAlert"] { border-radius:4px; }
    header[data-testid="stHeader"] { background:#ffffff !important; border-bottom:1px solid #dfe6ec; }
    [data-testid="stToolbar"], [data-testid="stToolbar"] * { color:#526475 !important; }
    .stTextInput div[data-baseweb="input"] > div { background:#ffffff !important; border:1px solid #b8c5d0; border-radius:4px; }
    .stTextInput div[data-baseweb="input"] input { color:var(--axon-text) !important; background:transparent !important; }
    [data-testid="stFileUploaderDropzone"] { background:#ffffff !important; border:1px dashed #b8c5d0 !important; border-radius:4px !important; }
    [data-testid="stFileUploaderDropzone"] * { color:var(--axon-text) !important; }
    [data-testid="stFileUploaderDropzone"] button { background:#f2f5f7 !important; border:1px solid #b8c5d0 !important; border-radius:4px !important; color:var(--axon-text) !important; }
    [data-testid="stAlert"] * { color:#314354 !important; }
    [data-testid="stExpander"] { border:1px solid #d9e1e8; border-radius:4px; background:#ffffff; }
    [data-testid="stExpander"] summary { color:#314354; font-weight:650; }
    @media (max-width: 760px) { .axon-hero { padding:22px; display:block; } .axon-chip { display:inline-block; margin-top:16px; } .part-grid { grid-template-columns:1fr; } }
</style>
""", unsafe_allow_html=True)


def hero(status_text="EDGE MODEL ONLINE"):
    st.markdown(f"""<div class='axon-hero'>
      <div><div class='axon-kicker'>AXON · EDGE DIAGNOSTICS</div><h1>Bearing diagnostics</h1>
      <p>Local vibration analysis, model decisions, and maintenance evidence in one workspace.</p></div>
      <div class='axon-chip'>{status_text}</div>
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


COMPONENT_LABELS = {
    "bearing-drive-end": "Drive-end bearing",
    "bearing-non-drive-end": "Non-drive-end bearing",
}


def component_label(diagnostic):
    component = (diagnostic or {}).get("component_id", "bearing-drive-end")
    return COMPONENT_LABELS.get(component, component.replace("-", " ").replace("_", " ").title())


def diagnostic_source(diagnostic):
    """Describe the recorded path without assuming a hardware device is online."""
    if not diagnostic:
        return "Waiting for a LoRa diagnostic", "No diagnostic has arrived from the Raspberry Pi for this asset yet.", "waiting"
    evidence = (diagnostic or {}).get("evidence") or []
    source = next((item.get("source") for item in evidence if item.get("source")), None)
    if source == "lora_uart":
        return "LoRa gateway result", "Received from the Raspberry Pi through the point-to-point LoRa gateway.", "live"
    if source == "manual_csv_replay":
        return "Manual CSV replay", "A saved vibration window was submitted from this dashboard.", "waiting"
    return "Recorded diagnostic", "This older result has no source tag; new edge events are tagged automatically.", "waiting"


def bearing_schematic(diagnostic):
    """Show the real reported component with a compact 3D-style bearing view."""
    diagnostic = diagnostic or {}
    location = diagnostic.get("fault_location")
    status = diagnostic.get("status")
    suspected = status in {"FAULT_SUSPECTED", "FAULT_CONFIRMED"}
    confirmed = status == "FAULT_CONFIRMED"
    label = component_label(diagnostic)
    fault_color, neutral = "#dc2626", "#64748b"

    # Generic Paderborn damage supports an assembly-level service action only.
    # If a later validated model supplies a race-level location, this visual
    # narrows the red highlight to that specific bearing element.
    outer = fault_color if location == "outer_race" else neutral
    inner = fault_color if location == "inner_race" else neutral
    ball = fault_color if location == "rolling_element" else neutral
    assembly_alert = suspected and location is None
    component_color = fault_color if suspected else "#94a3b8"
    housing_fill = "url(#alertHousing)" if assembly_alert else "url(#housing)"
    if assembly_alert:
        scope = "Bearing assembly service region"
    elif location == "outer_race":
        scope = "Outer race"
    elif location == "inner_race":
        scope = "Inner race"
    elif location == "rolling_element":
        scope = "Rolling elements"
    else:
        scope = "No current fault location"
    state = "Technician-confirmed" if confirmed else "Model-predicted / unverified"

    st.markdown(f"""<div class='bearing-stage'>
      <div class='bearing-stage-title'>LIVE COMPONENT MODEL · {label.upper()}</div>
      <svg viewBox='0 0 700 310' role='img' aria-label='3D-style bearing model for {label}'>
        <defs>
          <linearGradient id='motor' x1='0' x2='1'><stop stop-color='#f8fafc'/><stop offset='.5' stop-color='#dbe4ec'/><stop offset='1' stop-color='#b9c7d3'/></linearGradient>
          <linearGradient id='shaft' x1='0' x2='0' y1='0' y2='1'><stop stop-color='#91a4b7'/><stop offset='.5' stop-color='#f8fafc'/><stop offset='1' stop-color='#71849a'/></linearGradient>
          <linearGradient id='housing' x1='0' x2='1'><stop stop-color='#dce5ed'/><stop offset='.5' stop-color='#f8fafc'/><stop offset='1' stop-color='#afc0cd'/></linearGradient>
          <linearGradient id='alertHousing' x1='0' x2='1'><stop stop-color='#fee2e2'/><stop offset='.5' stop-color='#fffafa'/><stop offset='1' stop-color='#fecaca'/></linearGradient>
          <radialGradient id='steel'><stop stop-color='#ffffff'/><stop offset='.56' stop-color='#d4dde6'/><stop offset='1' stop-color='#718399'/></radialGradient>
          <filter id='shadow' x='-20%' y='-20%' width='140%' height='140%'><feDropShadow dx='0' dy='6' stdDeviation='5' flood-color='#64748b' flood-opacity='.23'/></filter>
        </defs>
        <rect x='26' y='101' width='135' height='108' rx='3' fill='url(#motor)' stroke='#64748b' stroke-width='3'/>
        <rect x='39' y='115' width='13' height='80' fill='#c0ceda'/><text x='93' y='159' text-anchor='middle' fill='#334155' font-size='16' font-weight='700'>Motor</text>
        <rect x='157' y='142' width='227' height='24' rx='4' fill='url(#shaft)' stroke='#64748b' stroke-width='2'/>
        <g filter='url(#shadow)'>
          <rect x='382' y='69' width='144' height='170' rx='3' fill='{housing_fill}' stroke='{component_color}' stroke-width='{4 if suspected else 3}'/>
          <ellipse cx='382' cy='154' rx='48' ry='85' fill='#d7e1e9' stroke='{component_color}' stroke-width='{4 if assembly_alert else 3}'/>
          <ellipse cx='526' cy='154' rx='48' ry='85' fill='url(#steel)' stroke='{component_color}' stroke-width='{4 if assembly_alert else 3}'/>
          <ellipse cx='526' cy='154' rx='34' ry='66' fill='#f8fafc' stroke='{outer}' stroke-width='13'/>
          <ellipse cx='526' cy='154' rx='14' ry='30' fill='#ffffff' stroke='{inner}' stroke-width='11'/>
          <ellipse cx='526' cy='103' rx='9' ry='13' fill='{ball}'/><ellipse cx='557' cy='126' rx='9' ry='13' fill='{ball}'/>
          <ellipse cx='557' cy='182' rx='9' ry='13' fill='{ball}'/><ellipse cx='526' cy='205' rx='9' ry='13' fill='{ball}'/>
          <ellipse cx='495' cy='182' rx='9' ry='13' fill='{ball}'/><ellipse cx='495' cy='126' rx='9' ry='13' fill='{ball}'/>
        </g>
        <text x='454' y='27' text-anchor='middle' fill='#64748b' font-size='12' font-weight='700'>SERVICE REGION</text>
        <text x='454' y='48' text-anchor='middle' fill='{component_color}' font-size='14' font-weight='700'>{scope}</text>
        <text x='454' y='272' text-anchor='middle' fill='#526475' font-size='13'>{label} · sensor target</text>
        <text x='26' y='282' fill='#526475' font-size='13'>{state}. Component ID: {diagnostic.get('component_id', 'bearing-drive-end')}.</text>
      </svg>
      <div class='bearing-stage-note'>The 3D view follows the newest saved diagnostic. It highlights only the component or bearing feature supplied by the validated model.</div>
    </div>""", unsafe_allow_html=True)
    if suspected and location is None:
        st.warning(f"The model has flagged the {label.lower()} assembly. It does not have validated evidence to colour an inner race, outer race, or rolling element red.")
    else:
        st.caption("Red is a model hypothesis, not physical confirmation. Grey means no evidence supports that subcomponent.")


def component_status_table(diagnostic):
    """Translate one diagnostic into an explicit per-part operator view."""
    diagnostic = diagnostic or {}
    status, location = diagnostic.get("status"), diagnostic.get("fault_location")
    suspected = status in {"FAULT_SUSPECTED", "FAULT_CONFIRMED"}
    healthy = status == "HEALTHY_WITHIN_VALIDATED_SCOPE"
    label = component_label(diagnostic)
    exact_location = {
        "inner_race": "Inner race",
        "outer_race": "Outer race",
        "rolling_element": "Rolling elements",
    }.get(location)
    rows = [
        (
            label,
            "FAULT SUSPECTED" if suspected else "HEALTHY WITHIN SCOPE" if healthy else "AWAITING DIAGNOSTIC",
            f"Inspect or replace this {label.lower()} assembly" if suspected else "No damage detected by the deployed model" if healthy else "Await the next edge vibration window for this component",
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
    section_title("Part-by-part status", "The live model identifies the sensor-targeted bearing. Red narrows to a race or rolling element only when the model has validated that conclusion.")
    st.markdown(f"<div class='part-grid'>{cards}</div>", unsafe_allow_html=True)


def bearing_diagnosis_panel():
    status, status_error = fetch("/diagnostics/model-status")
    hero("EDGE MODEL ONLINE" if not status_error and status and status.get("available") else "MODEL CHECK REQUIRED")
    section_title("Bearing diagnostic workspace", "The Raspberry Pi edge path is primary: local sensor window → Pi inference → LoRa summary → gateway diagnostic. This view refreshes automatically.")
    input_column, contract_column = st.columns((1.25, .75), gap="large")
    with input_column:
        asset_id = st.text_input("Asset ID", value="demo-motor-001", help="Must match the asset_id sent by the Raspberry Pi edge publisher.")
    with contract_column:
        if status and status.get("available"):
            contract = status["input_contract"]
            st.markdown("<div class='diagnostic-card'><div class='diagnostic-eyebrow'>RASPBERRY PI INPUT CONTRACT</div>"
                        f"<div class='diagnostic-value'>{contract['sampling_frequency_hz']:,.0f} Hz vibration</div>"
                        f"<div class='diagnostic-detail'>{contract['window_samples']:,} samples per edge window · {len(contract['feature_names'])} engineered features</div></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='diagnostic-card'><div class='diagnostic-eyebrow'>INPUT CONTRACT</div><div class='diagnostic-value'>Unavailable</div><div class='diagnostic-detail'>Deploy a validated bundle before uploading data.</div></div>", unsafe_allow_html=True)
    if status_error:
        st.error(f"Diagnostic API unavailable: {status_error}"); return
    if not status or not status.get("available"):
        st.warning(f"Bearing model unavailable: {(status or {}).get('reason', 'no validated bundle is deployed')}")
        st.caption("No bearing fault label, location, cost, or repair instruction is inferred while the model is unavailable.")
        return

    st.success(f"Active model: {status['model_version']} · {status['kind'].replace('_', ' ')}")
    with st.expander("Manual CSV replay (optional)", expanded=False):
        st.caption("This is a troubleshooting and demo fallback. The normal Raspberry Pi route sends a compact diagnostic summary over LoRa, so no file is needed during live operation.")
        upload = st.file_uploader("Recorded vibration window CSV", type=["csv"], help="Use only a recorded window with the active model's sample count and sampling frequency.")
        if upload is not None:
            window = pd.read_csv(upload).select_dtypes(include="number")
            if window.empty:
                st.error("The upload has no numeric vibration column.")
            elif st.button("Replay recorded window", type="primary", use_container_width=True):
                contract = status["input_contract"]
                with st.spinner("Running local diagnostic replay..."):
                    result, error = post_json("/diagnostics/infer", {"asset_id": asset_id, "component_id": "bearing-drive-end", "signal": window.iloc[:, 0].tolist(), "sampling_frequency_hz": contract["sampling_frequency_hz"]})
                if error:
                    st.error(error)
                else:
                    st.success(f"Replay record {result['event_id']} created. The live result below will refresh automatically.")

    @st.fragment(run_every=f"{REFRESH}s")
    def live_diagnostic_panel(selected_asset):
        history, history_error = fetch("/diagnostics/history", asset_id=selected_asset, limit=20)
        ready, ready_error = fetch("/ready")
        if history_error:
            st.info("No diagnostic history is currently available.")
            return
        latest = history[0] if history else None
        source_title, source_detail, source_tone = diagnostic_source(latest)
        transport_state = "LoRa gateway API ready" if not ready_error and ready and ready.get("transport") == "lora_gateway_http" else "LoRa gateway API unavailable"
        event_time = latest.get("timestamp", "Awaiting event") if latest else "Awaiting edge event"
        st.markdown(f"""<div class='stream-card'>
          <div class='stream-indicator {source_tone}'></div>
          <div class='stream-copy'><div class='stream-title'>{source_title}</div><div class='stream-detail'>{source_detail} Raspberry Pi diagnostics appear here after gateway delivery.</div></div>
          <div class='stream-meta'>{transport_state}<br/>{event_time}</div>
        </div>""", unsafe_allow_html=True)
        section_title(f"Latest diagnostic · auto-refreshes every {REFRESH}s", "The bearing model and decision panel are rebuilt from the newest saved edge result for this asset.")
        left, right = st.columns((1.18, .82), gap="large")
        with left:
            st.markdown("### Component localization")
            bearing_schematic(latest)
            component_status_table(latest)
        with right:
            st.markdown("### Diagnostic decision")
            if latest:
                suspected = latest.get("status") in {"FAULT_SUSPECTED", "FAULT_CONFIRMED"}
                affected = component_label(latest)
                if suspected:
                    location = {"inner_race": "inner race", "outer_race": "outer race", "rolling_element": "rolling elements"}.get(latest.get("fault_location"))
                    detail = f"Validated model evidence points to the {location}." if location else f"Inspect or replace the {affected.lower()} assembly. The model does not claim an unvalidated race-level location."
                    st.markdown(f"<div class='diagnostic-card alert'><div class='diagnostic-eyebrow'>AFFECTED COMPONENT · {latest.get('component_id')}</div><div class='diagnostic-value'>{affected}</div><div class='diagnostic-detail'>{detail}</div></div>", unsafe_allow_html=True)
                elif latest.get("status") == "HEALTHY_WITHIN_VALIDATED_SCOPE":
                    st.markdown(f"<div class='diagnostic-card good'><div class='diagnostic-eyebrow'>MODEL DECISION · {latest.get('component_id')}</div><div class='diagnostic-value'>{affected}: healthy within scope</div><div class='diagnostic-detail'>No bearing damage was detected by the deployed model for this edge window.</div></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='diagnostic-card'><div class='diagnostic-eyebrow'>MODEL DECISION</div><div class='diagnostic-value'>No actionable localization</div><div class='diagnostic-detail'>The result does not support a component-level service action.</div></div>", unsafe_allow_html=True)
                metric_left, metric_right = st.columns(2)
                metric_left.metric("Confidence", f"{latest.get('confidence', 0):.0%}" if latest.get("confidence") is not None else "Unavailable")
                short_status = {"FAULT_SUSPECTED": "Fault", "FAULT_CONFIRMED": "Verified", "HEALTHY_WITHIN_VALIDATED_SCOPE": "Healthy"}.get(latest.get("status"), "Unavailable")
                metric_right.metric("Status", short_status)
                st.markdown(f"**Detected bearing**  \n`{affected}`")
                st.markdown(f"**Race-level location**  \n`{latest.get('fault_location') or 'Not localized'}`")
                with st.expander("Technical diagnostic record"):
                    st.json({key: latest.get(key) for key in ("timestamp", "asset_id", "component_id", "status", "fault_class", "fault_location", "confidence", "confidence_calibrated", "model_version", "evidence", "missing_information")})
            else:
                st.info("Waiting for a Raspberry Pi edge diagnostic for this asset. Manual CSV replay is optional and is available above.")
        with st.expander("Repair intelligence and cost", expanded=False):
            documents, document_error = fetch("/repair-documents/search", query="bearing")
            if document_error or documents.get("status") == "unavailable":
                st.warning("No applicable authorized repair documentation is configured.")
            else:
                st.dataframe(pd.DataFrame(documents["documents"]), use_container_width=True, hide_index=True)
            st.caption("Prices, compatible parts, and repair procedures remain unavailable until an authorized catalogue and equipment-specific documentation are configured.")
        if history:
            section_title("Diagnostic history", "Each result remains auditable by asset, timestamp, component, model status, and confidence.")
            history_frame = pd.DataFrame(history)
            visible_columns = [column for column in ("timestamp", "status", "component_id", "fault_class", "confidence", "model_version") if column in history_frame]
            st.dataframe(history_frame[visible_columns], use_container_width=True, hide_index=True)

    live_diagnostic_panel(asset_id)


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
    section_title("Operator controls", "Commands are queued for a LoRa-enabled edge receiver. Verify equipment execution from edge telemetry or at the machine.")
    st.caption("Queueing a command does not confirm LoRa delivery or machine execution. Verify both from edge telemetry or the edge terminal.")
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
