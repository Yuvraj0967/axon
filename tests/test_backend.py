from datetime import datetime, timezone

from backend.main import Alert, Command, DiagnosticEvent, MemoryStore, Telemetry, create_app


def diagnostic_payload():
    return {
        "event_id": "event-1", "timestamp": datetime.now(timezone.utc).isoformat(), "asset_id": "asset-1",
        "component_id": "bearing-drive-end", "fault_class": None, "fault_location": None, "confidence": None,
        "confidence_calibrated": False, "status": "MODEL_UNAVAILABLE", "evidence": [],
        "alternative_hypotheses": [], "missing_information": ["no model"],
        "recommended_confirmation_tests": [], "repair_reference_ids": [], "cost_estimate_id": None,
        "model_version": None, "requires_technician_confirmation": True, "simulated": False,
    }


def test_http_ingest_and_command_queue_contract():
    store = MemoryStore(); app = create_app(store=store)
    endpoints = {route.path: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
    now = datetime.now(timezone.utc).isoformat()
    endpoints["/ingest/telemetry"](Telemetry(machine_id="M1", ts=now, temp=73, vibration=0.3, current=4.5))
    endpoints["/ingest/alert"](Alert(machine_id="M1", ts=now, type="anomaly", score=0.4))
    assert endpoints["/machines"]() == ["M1"]
    assert len(endpoints["/readings"]("M1", 5)) == 1
    assert len(endpoints["/alerts"]("M1")) == 1
    result = endpoints["/command"](Command(machine_id="M1", action="slow_down", issued_by="test"))
    assert result["status"] == "queued_for_lora"
    assert endpoints["/ready"]()["transport"] == "lora_gateway_http"


def test_lora_gateway_diagnostic_is_persisted():
    store = MemoryStore(); app = create_app(store=store)
    endpoints = {route.path: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
    result = endpoints["/ingest/diagnostic"](DiagnosticEvent.model_validate(diagnostic_payload()))
    assert result["status"] == "accepted"
    assert store.diagnostics("asset-1")[0]["event_id"] == "event-1"


def test_diagnostic_and_cost_routes_are_explicit_when_no_bearing_model_is_deployed():
    store = MemoryStore(); app = create_app(store=store)
    endpoints = {route.path: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
    from backend.main import CostEstimateRequest, DiagnosticRequest
    result = endpoints["/diagnostics/infer"](DiagnosticRequest(asset_id="demo-asset", component_id="bearing-drive-end", signal=[0.0] * 64, sampling_frequency_hz=64000))
    assert result["status"] == "MODEL_UNAVAILABLE"
    assert endpoints["/diagnostics/history"]("demo-asset", 50)[0]["event_id"] == result["event_id"]
    estimate = endpoints["/cost-estimates"](CostEstimateRequest(line_items=[{"description": "bearing", "quantity": 1}], currency="INR"))
    assert estimate["estimate_status"] == "incomplete" and estimate["total"] is None
