"""Turn a persistent warning into a repair proposal the owner can approve.

Everything here is a pure function of the diagnostic history and the shop
registry, so it is deterministic, testable and runs with no network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from agent.registry import WEEKDAYS, find_asset, named

SUSPECTED = {"FAULT_SUSPECTED", "FAULT_CONFIRMED"}
DECISIVE = SUSPECTED | {"HEALTHY_WITHIN_VALIDATED_SCOPE"}
RECENT_EVENTS = 5           # how many recent decisive results are considered
MINIMUM_SUSPECTED = 3       # how many of them must be suspected before the owner is told
EPISODE_ENDS_AFTER = 3      # consecutive healthy results that end a warning episode
SNOOZE = timedelta(hours=24)  # a "not now" is raised again after this, if the warning persists
STEPS = ("request_technician", "check_part")
FINDINGS = ("fault_confirmed", "no_fault_found", "repaired")

_COMPONENTS = {
    "bearing-drive-end": {"en": "motor-side bearing", "hi": "मोटर की तरफ़ की बेयरिंग"},
    "bearing-non-drive-end": {"en": "far-side bearing", "hi": "दूसरी तरफ़ की बेयरिंग"},
}
_WEEKDAY_NAMES = {
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "hi": ("सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"),
}
# Plain-language reading of the vibration features, by direction of change.
_FEATURE_WORDS = {
    "strength": ({"rms", "std", "variance", "energy", "frequency_energy", "low_band_energy"},
                 {"higher": {"en": "it is vibrating harder", "hi": "कंपन बढ़ गया है"},
                  "lower": {"en": "it is vibrating less than usual", "hi": "कंपन सामान्य से कम है"}}),
    "knocks": ({"kurtosis", "crest_factor", "peak_amplitude", "peak_to_peak", "skewness"},
               {"higher": {"en": "there are sharp knocks in the vibration", "hi": "कंपन में तेज़ झटके आ रहे हैं"},
                "lower": {"en": "the vibration has lost its usual peaks", "hi": "कंपन के सामान्य झटके कम हो गए हैं"}}),
    "pitch": ({"dominant_frequency_hz", "spectral_centroid_hz", "spectral_entropy", "high_band_energy", "mean"},
              {"higher": {"en": "the sound has become higher-pitched", "hi": "आवाज़ पहले से पतली हो गई है"},
               "lower": {"en": "the sound has become lower-pitched", "hi": "आवाज़ पहले से भारी हो गई है"}}),
}


def _when(value) -> datetime:
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _baseline_evidence(event: dict) -> dict | None:
    return next((item for item in event.get("evidence", []) if item.get("detector") == "healthy_only_baseline"), None)


def assess(history: list[dict], now: datetime | None = None) -> dict | None:
    """Decide whether the recent results amount to a warning worth raising.

    ``history`` is newest first. One unusual window is not a warning: at least
    MINIMUM_SUSPECTED of the last RECENT_EVENTS decisive results must agree.
    """
    now = now or datetime.now(timezone.utc)
    decisive = [event for event in history if event.get("status") in DECISIVE]
    recent = decisive[:RECENT_EVENTS]
    suspected = [event for event in recent if event["status"] in SUSPECTED]
    if len(suspected) < MINIMUM_SUSPECTED:
        return None
    # Walk back to where this episode began: the oldest suspected result before
    # a run of healthy ones.
    first, healthy_run = suspected[-1], 0
    for event in decisive:
        if event["status"] in SUSPECTED:
            first, healthy_run = event, 0
        else:
            healthy_run += 1
            if healthy_run >= EPISODE_ENDS_AFTER:
                break
    started = _when(first["timestamp"])
    duration = max(now - started, timedelta(0))
    ratios = [evidence["drift_ratio"] for evidence in map(_baseline_evidence, suspected) if evidence and evidence.get("drift_ratio")]
    drift_ratio = max(ratios) if ratios else None
    every_result_suspected = len(suspected) == len(recent)
    urgent = every_result_suspected and (duration >= timedelta(days=2) or (drift_ratio is not None and drift_ratio >= 1.5))
    latest_evidence = _baseline_evidence(suspected[0])
    return {
        "urgency": "urgent" if urgent else "soon",
        "considered_events": len(recent), "suspected_events": len(suspected),
        "episode_started": started.isoformat(), "duration_seconds": int(duration.total_seconds()),
        "drift_ratio": drift_ratio,
        "detector": "healthy_only_baseline" if latest_evidence else "supervised_classifier",
        "changed_features": (latest_evidence or {}).get("changed_features", []),
        "evidence_event_ids": [event["event_id"] for event in suspected],
        "component_id": suspected[0].get("component_id"),
        "simulated": any(event.get("simulated") for event in suspected),
    }


def next_idle_window(shop: dict, now: datetime) -> dict | None:
    """The next idle window that has not already ended, in the shop's local time."""
    local_zone = timezone(timedelta(minutes=int(shop.get("utc_offset_minutes", 330))))
    local_now = now.astimezone(local_zone)
    candidates = []
    for offset in range(8):
        day = (local_now + timedelta(days=offset)).date()
        for window in shop.get("idle_windows", []):
            if WEEKDAYS[day.weekday()] != window["weekday"]:
                continue
            start_h, start_m = map(int, window["start"].split(":")); end_h, end_m = map(int, window["end"].split(":"))
            start = datetime(day.year, day.month, day.day, start_h, start_m, tzinfo=local_zone)
            end = datetime(day.year, day.month, day.day, end_h, end_m, tzinfo=local_zone)
            if end > local_now:
                candidates.append((start, end))
    if not candidates:
        return None
    start, end = min(candidates)
    return {"start": start.isoformat(), "end": end.isoformat(), "weekday": WEEKDAYS[start.weekday()]}


def _duration_words(seconds: int, language: str) -> str:
    days, hours, minutes = seconds // 86_400, seconds // 3_600, max(seconds // 60, 1)
    if language == "hi":
        return f"{days} दिन" if days else f"{hours} घंटे" if hours else f"{minutes} मिनट"
    if days:
        return f"{days} day{'s' if days != 1 else ''}"
    if hours:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def what_changed(assessment: dict, language: str) -> str:
    """Say what changed in words an owner would use, not feature names."""
    if assessment["detector"] != "healthy_only_baseline":
        return {"en": "its vibration matches bearing damage seen in lab recordings",
                "hi": "इसका कंपन लैब में दर्ज ख़राब बेयरिंग जैसा है"}[language]
    phrases = []
    for feature in assessment["changed_features"]:
        for names, words in _FEATURE_WORDS.values():
            if feature["feature"] in names:
                phrase = words[feature["direction"]][language]
                if phrase not in phrases:
                    phrases.append(phrase)
    if not phrases:
        return {"en": "its vibration has moved away from normal", "hi": "इसका कंपन सामान्य से हट गया है"}[language]
    return (" और " if language == "hi" else " and ").join(phrases[:2])


def _slot_words(slot: dict | None, language: str) -> str:
    if slot is None:
        return {"en": "No idle time is on record, so please tell me when the machine can be stopped.",
                "hi": "खाली समय दर्ज नहीं है, कृपया बताएँ कि मशीन कब रोकी जा सकती है।"}[language]
    start, end = datetime.fromisoformat(slot["start"]), datetime.fromisoformat(slot["end"])
    day = _WEEKDAY_NAMES[language][start.weekday()]
    span = f"{start:%H:%M}–{end:%H:%M}"
    if language == "hi":
        return f"{day} ({start:%d-%m}) को {span} मशीन खाली रहती है।"
    return f"{day} {start.day} {start:%b}, {span}, is idle."


def owner_message(asset_label: str, assessment: dict, slot: dict | None, language: str) -> str:
    component = _COMPONENTS.get(assessment.get("component_id"), {"en": "bearing", "hi": "बेयरिंग"})[language]
    duration = _duration_words(assessment["duration_seconds"], language)
    changed = what_changed(assessment, language)
    urgent = assessment["urgency"] == "urgent"
    if language == "hi":
        text = f"{asset_label}: {component} पिछले {duration} से सामान्य से अलग चल रही है — {changed}। "
        text += "यह तेज़ी से बढ़ रहा है, देर न करें। " if urgent else ""
        return text + f"{_slot_words(slot, language)} क्या मैं मिस्त्री को बुलाऊँ और पार्ट की उपलब्धता पूछूँ?"
    text = f"{asset_label}: the {component} has been running differently from normal for {duration} — {changed}. "
    text += "It is getting worse quickly, so I would not wait. " if urgent else ""
    return text + f"{_slot_words(slot, language)} Shall I ask the technician and check the part?"


def build_proposal(registry: dict, asset_id: str, assessment: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    located = find_asset(registry, asset_id)
    if located is None:
        raise KeyError(f"asset {asset_id} is not in the shop registry")
    shop, asset = located
    language = shop.get("language", "en")
    label = asset.get("label") or asset_id
    slot = next_idle_window(shop, now)
    component_id = assessment.get("component_id") or "bearing-drive-end"
    part = asset.get("parts", {}).get(component_id, {})
    part_words = part.get("description") or _COMPONENTS.get(component_id, {"en": "bearing"})["en"]
    if part.get("part_number"):
        part_words += f" (part {part['part_number']})"
    technician = named(registry, "technicians", "technician_id", shop.get("technician_id"))
    dealer = named(registry, "dealers", "dealer_id", shop.get("dealer_id"))
    slot_text = f"{slot['start']} to {slot['end']}" if slot else "a time the owner will confirm"
    steps = [
        {"step": "request_technician", "state": "awaiting_owner_approval", "recipient_id": shop.get("technician_id"),
         "recipient_name": (technician or {}).get("name"),
         "draft": f"{shop['name']}, {label}: {_COMPONENTS.get(component_id, {'en': 'bearing'})['en']} needs inspection "
                  f"({assessment['urgency']}). Proposed visit: {slot_text}. "
                  f"{assessment['suspected_events']} of the last {assessment['considered_events']} checks were abnormal."},
        {"step": "check_part", "state": "awaiting_owner_approval", "recipient_id": shop.get("dealer_id"),
         "recipient_name": (dealer or {}).get("name"),
         "draft": f"{shop['name']}: is this in stock, and at what price? {part_words}, for {label}. "
                  f"Needed by {slot['start'] if slot else 'a date to be confirmed'}."},
    ]
    return {
        "proposal_id": str(uuid4()), "created": now.isoformat(), "updated": now.isoformat(),
        "asset_id": asset_id, "asset_label": label, "component_id": component_id,
        "shop_id": shop["shop_id"], "shop_name": shop["name"],
        "technician_id": shop.get("technician_id"), "dealer_id": shop.get("dealer_id"),
        "state": "awaiting_owner", "urgency": assessment["urgency"], "assessment": assessment,
        "owner_message": {"language": language, "text": owner_message(label, assessment, slot, language),
                          "delivery": "shown_in_dashboard_only"},
        "proposed_slot": slot, "steps": steps, "technician_finding": None,
        "simulated": assessment["simulated"],
        "policy": {"machine_control": "never", "owner_approval_required_per_step": True,
                   "outbound_messaging": "drafts_only_no_channel_configured"},
    }


def apply_decision(proposal: dict, step: str, decision: str, decided_by: str, now: datetime | None = None) -> dict:
    """Record the owner's answer for one step, or for every step with ``all``."""
    now = now or datetime.now(timezone.utc)
    if proposal["state"] == "closed":
        raise ValueError("this proposal is closed")
    if step != "all" and step not in STEPS:
        raise ValueError(f"step must be 'all' or one of {', '.join(STEPS)}")
    if decision not in {"approve", "not_now"}:
        raise ValueError("decision must be approve or not_now")
    for item in proposal["steps"]:
        if step in ("all", item["step"]):
            # Approval releases the draft for sending. No messaging channel is
            # wired up yet, so the draft waits here for a person to pass on.
            item.update(state="approved_ready_to_send" if decision == "approve" else "deferred",
                        decided_by=decided_by, decided_at=now.isoformat())
    states = {item["state"] for item in proposal["steps"]}
    proposal["state"] = ("approved" if "approved_ready_to_send" in states else
                         "deferred" if states == {"deferred"} else "awaiting_owner")
    proposal["updated"] = now.isoformat()
    return proposal


def record_finding(proposal: dict, technician_id: str, finding: str, notes: str | None = None, now: datetime | None = None) -> dict:
    """Close the proposal with what the technician found and note what it means for the baseline."""
    now = now or datetime.now(timezone.utc)
    if finding not in FINDINGS:
        raise ValueError(f"finding must be one of {', '.join(FINDINGS)}")
    feedback = {
        "no_fault_found": ("add_flagged_windows_to_healthy_reference", "The warning was a false alarm; refit this machine's baseline with these windows treated as normal."),
        "fault_confirmed": ("keep_as_fault_reference", "The warning was right; keep these windows as a confirmed fault example for this machine."),
        "repaired": ("refit_baseline_after_repair", "A repaired machine has a new normal; record healthy running again and refit the baseline."),
    }[finding]
    proposal["technician_finding"] = {"technician_id": technician_id, "finding": finding, "notes": notes, "recorded": now.isoformat(),
                                      "baseline_feedback": {"action": feedback[0], "reason": feedback[1], "applied": False}}
    proposal["state"], proposal["updated"] = "closed", now.isoformat()
    return proposal


def evaluate_asset(registry: dict, asset_id: str, history: list[dict], proposals: list[dict], now: datetime | None = None) -> tuple[str, dict | None]:
    """Run one agent pass for a machine. Returns (action, proposal)."""
    now = now or datetime.now(timezone.utc)
    if find_asset(registry, asset_id) is None:
        return "asset_not_registered", None
    open_proposal = next((item for item in proposals if item["state"] != "closed"), None)
    closed = [_when(item["updated"]) for item in proposals if item["state"] == "closed"]
    if closed:
        # Results from before the last technician visit belong to the old episode.
        history = [event for event in history if _when(event["timestamp"]) > max(closed)]
    assessment = assess(history, now)
    if open_proposal is not None:
        snoozed_out = open_proposal["state"] == "deferred" and now - _when(open_proposal["updated"]) >= SNOOZE
        if assessment is None or not snoozed_out:
            return "proposal_open", open_proposal
        refreshed = build_proposal(registry, asset_id, assessment, now)
        refreshed.update(proposal_id=open_proposal["proposal_id"], created=open_proposal["created"], raised_again=True)
        return "proposal_raised_again", refreshed
    if assessment is None:
        return "no_warning", None
    return "proposal_created", build_proposal(registry, asset_id, assessment, now)


def technician_worklist(registry: dict, technician_id: str, latest_by_asset: dict[str, dict | None], proposals_by_asset: dict[str, list[dict]]) -> list[dict]:
    """Rank every machine this technician serves, across shops, most pressing first."""
    rows = []
    for shop in registry.get("shops", []):
        if shop.get("technician_id") != technician_id:
            continue
        for asset in shop.get("assets", []):
            asset_id = asset["asset_id"]
            latest = latest_by_asset.get(asset_id)
            proposal = next((item for item in proposals_by_asset.get(asset_id, []) if item["state"] != "closed"), None)
            status = (latest or {}).get("status")
            if proposal:
                priority = 3 if proposal["urgency"] == "urgent" else 2
            else:
                priority = 1 if status in SUSPECTED else 0
            part = asset.get("parts", {}).get((proposal or {}).get("component_id", "bearing-drive-end"), {})
            visit_approved = bool(proposal) and any(item["step"] == "request_technician" and item["state"] == "approved_ready_to_send" for item in proposal["steps"])
            rows.append({
                "shop_id": shop["shop_id"], "shop_name": shop["name"], "asset_id": asset_id, "asset_label": asset.get("label") or asset_id,
                "priority": priority,
                "attention": ("urgent" if priority == 3 else "plan_repair" if priority == 2 else "watch" if priority == 1 else
                              "no_data" if latest is None else "normal"),
                "latest_status": status, "latest_result_at": (latest or {}).get("timestamp"),
                "drift_ratio": (proposal or {}).get("assessment", {}).get("drift_ratio"),
                "episode_started": (proposal or {}).get("assessment", {}).get("episode_started"),
                "proposal_id": (proposal or {}).get("proposal_id"), "proposal_state": (proposal or {}).get("state"),
                "owner_approved_visit": visit_approved,
                "proposed_slot": (proposal or {}).get("proposed_slot"),
                "part": part.get("description"), "part_number": part.get("part_number"),
            })
    rows.sort(key=lambda row: (-row["priority"], -(row["drift_ratio"] or 0), row["episode_started"] or "9999", row["shop_name"], row["asset_label"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows
