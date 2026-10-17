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
st.set_page_config(page_title="Axon", layout="wide")
st.title("Axon | Machine Intelligence")
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
        # A generic documented-damage model identifies the bearing component,
        # rather than claiming a race-level location it was not trained to infer.
        outer = inner = ball = fault_color
        detail = "Race position not localized by this model"
    else:
        outer = fault_color if location == "outer_race" else neutral
        inner = fault_color if location == "inner_race" else neutral
        ball = fault_color if location == "rolling_element" else neutral
        detail = "No fault localized" if status else "Awaiting a diagnostic event"
    state = "Technician-confirmed" if confirmed else "Model-predicted / unverified"
    component_color = fault_color if suspected else "#94a3b8"
    st.markdown(f"""<svg viewBox='0 0 480 210' role='img' aria-label='drive-end bearing component map' style='max-width:520px'>
    <rect x='18' y='66' width='108' height='78' rx='10' fill='#e2e8f0' stroke='#64748b' stroke-width='3'/>
    <text x='72' y='111' text-anchor='middle' fill='#334155' font-size='15'>Motor</text>
    <line x1='126' y1='105' x2='315' y2='105' stroke='#64748b' stroke-width='14' stroke-linecap='round'/>
    <rect x='304' y='54' width='76' height='102' rx='12' fill='{component_color}' opacity='0.18' stroke='{component_color}' stroke-width='6'/>
    <text x='342' y='180' text-anchor='middle' fill='{component_color}' font-size='14' font-weight='bold'>Drive-end bearing</text>
    <circle cx='430' cy='105' r='66' fill='none' stroke='{outer}' stroke-width='15'/>
    <circle cx='430' cy='105' r='31' fill='none' stroke='{inner}' stroke-width='15'/>
    <circle cx='430' cy='52' r='9' fill='{ball}'/><circle cx='483' cy='105' r='9' fill='{ball}'/><circle cx='430' cy='158' r='9' fill='{ball}'/><circle cx='377' cy='105' r='9' fill='{ball}'/>
    <text x='18' y='204' fill='#475569' font-size='13'>{state}: {component}. {detail}.</text></svg>""", unsafe_allow_html=True)
    if suspected and location is None:
        st.warning("Red identifies the drive-end bearing as the affected component. The deployed model does not make an unsupported inner- or outer-race claim.")
    else:
        st.caption("Red is a model hypothesis, not physical confirmation. Grey means unavailable or unsupported.")


def bearing_diagnosis_panel():
    st.subheader("Bearing diagnosis | evidence-grounded workflow")
    asset_id = st.text_input("Asset ID", value="demo-motor-001")
    status, status_error = fetch("/diagnostics/model-status")
    if status_error:
        st.error(f"Diagnostic API unavailable: {status_error}"); return
    if not status.get("available"):
        st.warning(f"Bearing model unavailable: {status.get('reason', 'no validated bundle is deployed')}")
        st.caption("No bearing fault label, location, cost, or repair instruction is inferred while the model is unavailable.")
    else:
        st.success(f"Active model: {status['model_version']} ({status['kind']})")
        upload = st.file_uploader("Vibration window CSV", type=["csv"], help="A single numeric vibration channel matching the deployed model's exact window length and sampling frequency.")
        if upload is not None:
            window = pd.read_csv(upload).select_dtypes(include="number")
            if window.empty: st.error("The upload has no numeric vibration column.")
            elif st.button("Run local-model diagnostic"):
                contract = status["input_contract"]
                result, error = post_json("/diagnostics/infer", {"asset_id": asset_id, "component_id": "bearing-drive-end", "signal": window.iloc[:, 0].tolist(), "sampling_frequency_hz": contract["sampling_frequency_hz"]})
                if error: st.error(error)
                else: st.success(f"Diagnostic record {result['event_id']} created.")
    history, history_error = fetch("/diagnostics/history", asset_id=asset_id, limit=20)
    if history_error:
        st.info("No diagnostic history is currently available."); return
    latest = history[0] if history else None
    left, right = st.columns((1, 1))
    with left:
        st.subheader("Component localization")
        bearing_schematic(latest)
    with right:
        st.subheader("Current diagnostic")
        if latest:
            st.json({key: latest.get(key) for key in ("status", "fault_class", "fault_location", "confidence", "confidence_calibrated", "model_version", "missing_information")})
        else: st.info("No persisted diagnostic event for this asset.")
    st.subheader("Repair intelligence and cost")
    documents, document_error = fetch("/repair-documents/search", query="bearing")
    if document_error or documents.get("status") == "unavailable":
        st.warning("No applicable authorized repair documentation is configured.")
    else: st.dataframe(pd.DataFrame(documents["documents"]), use_container_width=True)
    st.caption("Prices, compatible parts, and repair procedures remain unavailable until an authorized catalogue and equipment-specific documentation are configured.")
    if history: st.subheader("Auditable diagnostic history"); st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)


view = st.sidebar.radio("Data view", ("Bearing diagnosis", "Live simulator"))
if view == "Bearing diagnosis":
    st.sidebar.success("Source: Paderborn Bearing DataCenter vibration recordings")
    bearing_diagnosis_panel()
else:
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
        st.caption(f"Telemetry: {freshness}; latest reading: {df.index[-1].isoformat() if not df.empty else 'none'}")
        status = health.get("status", "unknown")
        {"healthy": st.success, "warning": st.warning, "critical": st.error}.get(status, st.info)(f"Machine status: {status.upper()}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Health score", health.get("score", "-"))
        c2.metric("Temperature trend", health.get("temp_slope", "-"))
        c3.metric("Minutes to limit", health.get("minutes_to_limit") if health.get("minutes_to_limit") is not None else "-")
        c4.metric("Alerts", len(alerts))
        if df.empty: st.info("No telemetry has arrived for this machine yet.")
        else:
            st.subheader("Sensors")
            st.line_chart(df[["temp", "vibration", "current"]])
        left, right = st.columns(2)
        left.subheader("Alert feed"); left.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
        right.subheader("Command history"); right.dataframe(pd.DataFrame(commands), use_container_width=True, hide_index=True)

    live_panel()
    st.subheader("Operator controls")
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
