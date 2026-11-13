# Repair-coordination agent

After a warning, the agent does the legwork that the owner would otherwise do by phone: it explains what changed, proposes a repair slot in an idle window, and prepares the technician request and the part enquiry.

Two rules hold everywhere:

- **AXON never controls a machine.** There is no stop, slow or resume path. `POST /command` returns HTTP 501.
- **The owner approves each step.** A draft is released only after the owner approves that step.

The agent is rule-based (`agent/planner.py`) and reads a local JSON registry (`agent/registry.py`), so it runs with no internet and gives the same answer for the same history.

## What it does

1. **Decides whether there is a warning.** It looks at a machine's last 5 decisive results (healthy or suspected). At least 3 must be suspected. One unusual window is ignored.
2. **Works out how long and how urgent.** The episode starts at the oldest suspected result before a run of 3 healthy ones. It is `urgent` when all 5 recent results are suspected and either the episode is 2 or more days old or the drift score is at least 1.5 times the threshold. Otherwise it is `soon`.
3. **Explains it in the owner's language.** The message names the machine and component, how long it has been different, and what changed in plain words (harder vibration, sharp knocks, a change in pitch), taken from the baseline's changed features. English and Hindi are supported, set per shop.
4. **Proposes a slot.** It picks the shop's next idle window that has not already ended. If no idle hours are on record, it asks the owner for a time.
5. **Drafts two requests.** One to the technician for a visit, one to the dealer asking about stock and price for the part.
6. **Waits for the owner.** Each step is approved or answered "not now" separately. If every step is deferred and the warning is still there 24 hours later, the proposal is raised again with a fresh message.
7. **Records the technician's finding.** `fault_confirmed`, `repaired` or `no_fault_found` closes the proposal and stores what it means for that machine's baseline. Results from before the visit are not counted towards a new warning.

The agent runs on every diagnostic the gateway delivers. A failure in the agent never blocks storing the diagnostic.

## Shop registry

Copy `config/shops.example.json` to `config/shops.json` (ignored by git) or point `AXON_SHOPS_CONFIG` at a file. If neither exists, the example is used and the API marks it as example data.

Each shop lists its language (`en` or `hi`), UTC offset, weekly idle windows in local time, technician, dealer, and machines. A machine has an `asset_id` that must match the edge device, a label the owner recognises, and optionally the part for each component. A machine that is not in the registry gets no proposals.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /shops` | The registry the agent is using |
| `POST /agent/evaluate` | Run the agent for one machine now |
| `GET /agent/proposals` | Open proposals; filter with `asset_id`, `shop_id`, `include_closed` |
| `POST /agent/proposals/{id}/decision` | Owner's answer: `step` is `request_technician`, `check_part` or `all`; `decision` is `approve` or `not_now` |
| `POST /agent/proposals/{id}/finding` | Technician's finding; closes the proposal |
| `GET /technician/worklist?technician_id=` | Every machine the technician serves across shops, ranked |

The worklist ranks urgent proposals first, then other open proposals, then machines whose latest result is suspected, then the rest. Within a level, larger drift and older episodes come first. It shows whether the owner has approved the visit.

## Limits

- **No outbound messaging.** The owner's message and the approved drafts appear in the dashboard. No SMS, WhatsApp or phone channel is connected, so a person passes approved requests on.
- **No dealer integration.** The part enquiry is a draft; stock and price are not looked up.
- **Thresholds are starting values.** The 3-of-5 rule, the urgency rule and the 24-hour snooze have not been tuned on real shop data.
- **Baseline feedback is recorded, not applied.** Refitting a baseline after a finding is a manual step.
- **Hindi wording** was written for this project and has not been reviewed with shop owners.
