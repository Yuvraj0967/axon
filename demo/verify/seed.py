"""Seed a complete, honest demo tenant for AXON Verify.

Creates an organisation, a team, customers, sites, assets, devices and four
work orders that between them cover every verdict the policy can produce:

* a **verified** repair (certified) — documented damaged bearing before,
  documented healthy bearing after,
* a **not verified** repair — the fault is still indicated after the work,
* an **inconclusive** repair — the post-repair reading is genuinely uncertain,
* an **open** work order with no capture yet.

All evidence comes from the packaged Paderborn University windows (CC BY-NC-4.0)
and is permanently marked as replayed historical evidence, exactly as it would
be if it arrived over MQTT.

Usage::

    python demo/verify/seed.py --reset
    AXON_VERIFY_DB=var/axon-verify.db AXON_STORAGE_MODE=external \\
        uvicorn backend.main:app --port 8000

Then sign in as ``demo@axon.local`` with the demo password.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.auth import hash_password  # noqa: E402
from backend.ingest_service import accept_window_event  # noqa: E402
from backend.verification import default_policy, verify_repair  # noqa: E402
from backend.verify_routes import evidence_dict  # noqa: E402
from backend.verify_store import VerifyStore  # noqa: E402

DEFAULT_DATABASE = PROJECT_ROOT / "var" / "axon-verify.db"
DEMO_PASSWORD = os.getenv("AXON_DEMO_PASSWORD", "demo-axon-verify")

# Packaged windows and the role each plays in the story.
DAMAGED = "N09_M07_F10_KA04_1"    # documented damage, scored as damage
HEALTHY = "N09_M07_F10_K003_1"    # held-out healthy, scored as healthy
AMBIGUOUS = "N09_M07_F10_KI04_1"  # documented damage, model genuinely unsure

TEAM = [
    ("demo@axon.local", "Dana Okafor", "owner"),
    ("priya@acme.test", "Priya Raman", "manager"),
    ("sam@acme.test", "Sam technician", "technician"),
    ("northwind@customer.test", "Casey Northwind", "customer"),
]

ASSETS = [
    {"name": "Pump P-101", "serial": "SN-4471", "model": "CA20",
     "manufacturer": "Sulzer", "asset_type": "centrifugal_pump"},
    {"name": "Fan F-202", "serial": "SN-8812", "model": "HELIOFAN-900",
     "manufacturer": "Howden", "asset_type": "axial_fan"},
    {"name": "Compressor C-303", "serial": "SN-1290", "model": "ZR-160",
     "manufacturer": "Atlas Copco", "asset_type": "screw_compressor"},
    {"name": "Conveyor M-404", "serial": "SN-5567", "model": "Belt-1200",
     "manufacturer": "Flexco", "asset_type": "belt_conveyor"},
]

WORK_ORDERS = [
    {
        "asset": 0,
        "title": "Replace drive-end bearing after vibration alarm",
        "notes": "Customer reported a rise in overall vibration on the drive end. "
                 "Bearing replaced with a like-for-like unit.",
        "before": (DAMAGED, 0),
        "after": (HEALTHY, 0),
        "verify": True,
        "certify": True,
    },
    {
        "asset": 1,
        "title": "Investigate bearing noise on inlet side",
        "notes": "Technician re-greased and re-seated the bearing housing.",
        "before": (DAMAGED, 1),
        "after": (DAMAGED, 1),
        "verify": True,
        "certify": True,
    },
    {
        "asset": 2,
        "title": "Intermittent vibration on compressor stage",
        "notes": "Post-work reading was inconclusive; a repeat capture under load "
                 "is scheduled.",
        "before": (DAMAGED, 0),
        "after": (AMBIGUOUS, 0),
        "verify": True,
        "certify": True,
    },
    {
        "asset": 3,
        "title": "Scheduled bearing inspection",
        "notes": "Awaiting the site visit; no capture has been made yet.",
        "before": None,
        "after": None,
        "verify": False,
        "certify": False,
    },
]


def _capture(store: VerifyStore, org_id: str, asset: dict, component_id: str,
             recording_id: str, window_index: int, phase: str,
             captured_at: str) -> dict:
    from backend.paderborn_replay import read_window

    record, signal, sampling_frequency = read_window(recording_id, window_index)
    result = accept_window_event(
        store, org_id=org_id, asset_id=asset["id"], component_id=component_id,
        signal=[float(value) for value in signal.tolist()],
        sampling_frequency_hz=float(sampling_frequency),
        actor="demo-seed", transport="replay",
        operating_condition_id=record["operating_condition"], captured_at=captured_at)
    return result["diagnostic"]


def seed(database: Path, reset: bool = False, verbose: bool = True) -> dict:
    if reset and database.exists():
        database.unlink()
    database.parent.mkdir(parents=True, exist_ok=True)
    store = VerifyStore(str(database))

    def log(message: str) -> None:
        if verbose:
            print(message)

    org = store.create_org("Acme Industrial Services")
    org_id = org["id"]
    password_hash = hash_password(DEMO_PASSWORD, iterations=int(
        os.getenv("AXON_PBKDF2_ITERATIONS", "390000")))
    users = {}
    for email, name, role in TEAM:
        user = store.create_user(email, name, password_hash)
        store.add_membership(org_id, user["id"], role)
        users[email] = user

    customer = store.create_customer(org_id, "Northwind Mills")
    site = store.create_site(org_id, customer["id"], "Plant 1 — Gantry hall",
                             "Wellington, NZ")
    site_second = store.create_site(org_id, customer["id"], "Plant 2 — Packing line",
                                    "Hamilton, NZ")

    assets = []
    for index, spec in enumerate(ASSETS):
        asset = store.create_asset(
            org_id, site_id=site["id"] if index % 2 == 0 else site_second["id"],
            customer_id=customer["id"], **spec)
        component = store.create_component(org_id, asset["id"], "drive-end bearing",
                                           "bearing", "DE")
        store.create_component(org_id, asset["id"], "non-drive-end bearing",
                               "bearing", "NDE")
        assets.append({"asset": asset, "component": component})

    store.create_device(org_id, "Plant 1 vibration gateway", "plant1-gw-01",
                        "mqtt_gateway", site["id"],
                        cert_fingerprint="sha256:demo-fingerprint")
    store.create_device(org_id, "Packing line LoRa node", "packline-lora-02",
                        "lora_gateway", site_second["id"])
    store.create_api_key(org_id, "Historian export", "seeded-key-hash", "read")

    outcomes = []
    for spec in WORK_ORDERS:
        target = assets[spec["asset"]]
        order = store.create_work_order(
            org_id, asset_id=target["asset"]["id"], component_id=target["component"]["id"],
            title=spec["title"], notes=spec["notes"], customer_id=customer["id"],
            technician_id=users["sam@acme.test"]["id"],
            status="closed" if spec["verify"] else "open")
        repair = store.create_repair(org_id, order["id"], target["asset"]["id"],
                                     target["component"]["id"],
                                     "N09_M07_F10")
        diagnostics = {}
        for phase, captured in (("before", spec["before"]), ("after", spec["after"])):
            if captured is None:
                continue
            recording_id, window_index = captured
            timestamp = datetime.now(timezone.utc) - (
                timedelta(hours=30) if phase == "before" else timedelta(hours=2))
            diagnostics[phase] = _capture(
                store, org_id, target["asset"], target["component"]["id"],
                recording_id, window_index, phase, timestamp.isoformat())
            store.update_repair(org_id, repair["id"],
                                **{f"{phase}_diagnostic_id": diagnostics[phase]["id"]})

        verdict = None
        if spec["verify"] and len(diagnostics) == 2:
            reading_before = store.get_reading(org_id, diagnostics["before"]["reading_id"])
            reading_after = store.get_reading(org_id, diagnostics["after"]["reading_id"])
            before = evidence_dict(diagnostics["before"], reading_before)
            after = evidence_dict(diagnostics["after"], reading_after)
            result = verify_repair(before, after, default_policy(
                bool(before["confidence_calibrated"]) and
                bool(after["confidence_calibrated"])))
            verdict = result["verdict"]
            store.update_repair(
                org_id, repair["id"], verdict=verdict, reasons=result["reasons"],
                policy_version=result["policy"]["policy_version"],
                status="verified" if verdict == "VERIFIED" else "verification_complete",
                verified_at=datetime.now(timezone.utc).isoformat())
            if spec["certify"]:
                _issue_certificate(store, org_id, repair["id"], users["priya@acme.test"],
                                   target["asset"], target["component"])
        outcomes.append({"title": spec["title"], "verdict": verdict or "awaiting capture"})

    report = {
        "organisation": org["name"],
        "org_id": org_id,
        "site_id": site["id"],
        "database": str(database),
        "sign_in": "demo@axon.local",
        "password": DEMO_PASSWORD,
        "work_orders": outcomes,
        "devices": ["plant1-gw-01", "packline-lora-02"],
    }
    log(f"seeded {org['name']} into {database}")
    log(f"  sign in as {report['sign_in']} / {DEMO_PASSWORD}")
    for item in outcomes:
        log(f"  · {item['title']}: {item['verdict']}")
    log(f"  org_id={org_id} site_id={site['id']} device=plant1-gw-01")
    return report


def _issue_certificate(store: VerifyStore, org_id: str, repair_id: str, technician: dict,
                       asset: dict, component: dict) -> None:
    from backend.certificates import Signer, build_payload
    from backend.verification import verify_repair

    repair = store.get_repair(org_id, repair_id)
    before_diag = store.get_diagnostic(org_id, repair["before_diagnostic_id"])
    after_diag = store.get_diagnostic(org_id, repair["after_diagnostic_id"])
    before = evidence_dict(before_diag, store.get_reading(org_id, before_diag["reading_id"]))
    after = evidence_dict(after_diag, store.get_reading(org_id, after_diag["reading_id"]))
    result = verify_repair(before, after, default_policy(False))
    signer = Signer.resolve(store)
    certificate_id = f"AXV-{repair_id.upper().split('_')[-1][:12]}"
    payload = build_payload(
        org_name=store.get_org(org_id)["name"], repair=repair, asset=asset,
        component=component, before=before, after=after, result=result,
        policy=result["policy"],
        input_contract={
            "sensor_type": "vibration",
            "sampling_frequency_hz": before.get("sampling_frequency_hz"),
            "window_samples": before.get("window_samples"),
            "model_version": before.get("model_version"),
            "calibration_version": before.get("calibration_version"),
            "confidence_calibrated": False,
        },
        certificate_id=certificate_id,
        issued_at=datetime.now(timezone.utc).isoformat(),
        technician=technician["name"])
    store.create_certificate(org_id, repair_id, payload, signer.sign(payload),
                             signer.key_id)
    store.update_repair(org_id, repair_id, status="certified")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the AXON Verify demo tenant.")
    parser.add_argument("--database", default=os.getenv("AXON_VERIFY_DB",
                                                        str(DEFAULT_DATABASE)))
    parser.add_argument("--reset", action="store_true",
                        help="delete the existing database first")
    args = parser.parse_args(argv)
    report = seed(Path(args.database), reset=args.reset)
    print("\nstart the product with:")
    print(f"  AXON_VERIFY_DB={report['database']} \\")
    print("    uvicorn backend.main:app --host 0.0.0.0 --port 8000")
    print("then open http://localhost:8000/app/")
    print("\nnote: AXON_VERIFY_DB selects the verification store on its own; the legacy")
    print("telemetry store (InfluxDB/Postgres) is not needed for AXON Verify.")
    return 0


if __name__ == "__main__":  # pragma: no cover - operator tool
    raise SystemExit(main())
