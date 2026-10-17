import os, time
import pandas as pd
import requests
import streamlit as st

USE_MOCK = os.getenv("USE_MOCK", "0") == "1"
API = "http://" + os.getenv("BACKEND_IP", "localhost") + ":8000"
st.set_page_config(page_title="Axon", layout="wide")
st.title("Axon - Machine Health Dashboard")
machine = st.sidebar.selectbox("Machine", ["M1"])

def mock(path):
    if path == "/readings":
        return pd.read_csv("mock_readings.csv").to_dict("records")
    if path == "/health":
        return {"score": 42, "temp_slope": 0.3, "minutes_to_limit": 8.5, "status": "critical"}
    if path == "/alerts":
        return [{"machine_id": "M1", "ts": "mock", "type": "anomaly", "score": 0.8}]
    return []

def get(path, **params):
    if USE_MOCK:
        return mock(path)
    try:
        return requests.get(API + path, params=params, timeout=3).json()
    except Exception:
        return None

readings = get("/readings", machine_id=machine, minutes=5) or []
health = get("/health", machine_id=machine) or {}
alerts = get("/alerts", machine_id=machine) or []
cmds = get("/commands", machine_id=machine) or []

df = pd.DataFrame(readings)
if not df.empty:
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").set_index("ts")

status = health.get("status", "unknown")
if status == "critical":
    st.error("CRITICAL: machine health is low. Check alerts and consider slowing the machine down.")
elif status == "warning":
    st.warning("Warning: machine health is degrading.")
elif status == "healthy":
    st.success("Machine is healthy.")
else:
    st.info("Waiting for data from the backend...")

c1, c2, c3 = st.columns(3)
c1.metric("Health score", health.get("score", "-"))
mins = health.get("minutes_to_limit")
c2.metric("Minutes to temperature limit", mins if mins is not None else "-")
c3.metric("Alerts (last 50)", len(alerts))

if not df.empty:
    st.subheader("Temperature")
    st.line_chart(df[["temp"]])
    st.subheader("Vibration")
    st.line_chart(df[["vibration"]])
    st.subheader("Current")
    st.line_chart(df[["current"]])

left, right = st.columns(2)
left.subheader("Alert feed")
left.dataframe(pd.DataFrame(alerts), use_container_width=True)
right.subheader("Operator command history")
right.dataframe(pd.DataFrame(cmds), use_container_width=True)

st.subheader("Operator controls")
cols = st.columns(3)
for col, action in zip(cols, ("slow_down", "shutdown", "resume")):
    if col.button(action):
        if not USE_MOCK:
            requests.post(API + "/command", json={"machine_id": machine, "action": action})
        st.toast("Sent " + action)

time.sleep(2)
st.rerun()
