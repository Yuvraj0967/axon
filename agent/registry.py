"""Shop registry: which machine belongs to which shop, technician and dealer.

The registry is a local JSON file, so the agent works without internet. Copy
config/shops.example.json to config/shops.json and replace the example entries.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_SCHEMA = "axon-shop-registry-v1"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
LANGUAGES = ("en", "hi")


class RegistryError(ValueError):
    pass


def _clock(value) -> tuple[int, int]:
    try:
        hours, minutes = str(value).split(":")
        hours, minutes = int(hours), int(minutes)
    except ValueError as exc:
        raise RegistryError(f"idle window time {value!r} must be HH:MM") from exc
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise RegistryError(f"idle window time {value!r} is out of range")
    return hours, minutes


def validate_registry(data: dict) -> dict:
    if not isinstance(data, dict) or data.get("schema_version") != REGISTRY_SCHEMA:
        raise RegistryError(f"shop registry must declare schema_version {REGISTRY_SCHEMA}")
    technicians = {item["technician_id"] for item in data.get("technicians", [])}
    dealers = {item["dealer_id"] for item in data.get("dealers", [])}
    seen_assets: set[str] = set()
    for shop in data.get("shops", []):
        for key in ("shop_id", "name"):
            if not shop.get(key):
                raise RegistryError(f"every shop needs a {key}")
        if shop.get("language", "en") not in LANGUAGES:
            raise RegistryError(f"shop {shop['shop_id']}: language must be one of {', '.join(LANGUAGES)}")
        if shop.get("technician_id") and shop["technician_id"] not in technicians:
            raise RegistryError(f"shop {shop['shop_id']}: unknown technician_id {shop['technician_id']}")
        if shop.get("dealer_id") and shop["dealer_id"] not in dealers:
            raise RegistryError(f"shop {shop['shop_id']}: unknown dealer_id {shop['dealer_id']}")
        for window in shop.get("idle_windows", []):
            if window.get("weekday") not in WEEKDAYS:
                raise RegistryError(f"shop {shop['shop_id']}: idle window weekday must be a lowercase English weekday")
            if _clock(window.get("start")) >= _clock(window.get("end")):
                raise RegistryError(f"shop {shop['shop_id']}: idle window must end after it starts")
        for asset in shop.get("assets", []):
            asset_id = asset.get("asset_id")
            if not asset_id or asset_id in seen_assets:
                raise RegistryError(f"shop {shop['shop_id']}: asset_id is missing or registered twice: {asset_id!r}")
            seen_assets.add(asset_id)
    return data


def load_registry(path: Path | None = None) -> dict:
    """Load config/shops.json, or the packaged example when none is configured."""
    configured = path or os.getenv("AXON_SHOPS_CONFIG")
    candidates = [Path(configured)] if configured else [PROJECT_ROOT / "config" / "shops.json", PROJECT_ROOT / "config" / "shops.example.json"]
    for candidate in candidates:
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RegistryError(f"shop registry {candidate} is not valid JSON: {exc}") from exc
            registry = validate_registry(data)
            registry["example_data"] = candidate.name == "shops.example.json"
            return registry
    return {"schema_version": REGISTRY_SCHEMA, "technicians": [], "dealers": [], "shops": [], "example_data": False}


def find_asset(registry: dict, asset_id: str) -> tuple[dict, dict] | None:
    for shop in registry.get("shops", []):
        for asset in shop.get("assets", []):
            if asset.get("asset_id") == asset_id:
                return shop, asset
    return None


def named(registry: dict, collection: str, key: str, identifier: str | None) -> dict | None:
    return next((item for item in registry.get(collection, []) if item.get(key) == identifier), None)
