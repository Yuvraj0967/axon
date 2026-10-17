# Bearing diagnosis extension

## What is implemented

AXON's real-world data path is bearing-vibration data from Paderborn. It has a versioned taxonomy,
strict sampling/window validation, shared engineered features, group-aware
Random Forest training, an optional compact TensorFlow 1D CNN trainer, validated
Random Forest bundle loading, Raspberry Pi local inference, LoRa diagnostic summaries, API diagnostic records, and
a dashboard view with a result-driven bearing schematic.

The official Paderborn DataCenter provides vibration and motor-current data,
four operating conditions, and MATLAB recordings; it is licensed CC BY-NC 4.0,
requires attribution, and commercial use requires contacting the source. The
data is not downloaded or committed by AXON. See the [official dataset
page](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter) and its
[download description](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download).

## Reproducible workflow

1. Install the extra local ML requirements on a supported training host:

   ```powershell
   python -m pip install -r ml/requirements-bearing.txt
   ```

2. Copy `config/paderborn.example.json` outside Git, set `dataset_dir`, and
   add only mappings verified against the official Paderborn fact sheets.

3. Prepare locally acquired MAT files. Unmapped, corrupt, ambiguous, or
   non-finite recordings are written to `manifest.json` as exclusions rather
   than labelled as healthy. For constrained local storage,
   `max_recordings_per_bearing_condition` selects the first _n_ recordings in
   a deterministic numeric order for each physical-bearing/operating-condition
   pair; `0` preserves every recording.

   ```powershell
   python -m ml.data.prepare --config path/to/paderborn.local.json
   ```

4. Train the CPU-friendly reference model with whole physical bearings held
   out of training. This requires at least three independently labelled
   physical bearings for every included class (one each for train, validation,
   and test):

   ```powershell
   python -m ml.training.train_random_forest --prepared ml/data/paderborn/prepared/windows.npz --output ml/artifacts/bearing/rf-v1
   ```

5. Optionally train the 1D CNN on a TensorFlow-supported training host:

   ```powershell
   python -m ml.training.train_cnn --prepared ml/data/paderborn/prepared/windows.npz --output ml/artifacts/bearing/cnn-v1
   ```

   The CNN command honestly fails with an install instruction when TensorFlow
   is absent; it does not substitute a different model or claim an ONNX export.

6. Point the Pi/gateway at a checksum-validated Random Forest bundle and run
   the transparent-UART LoRa gateway:

   ```powershell
   $env:AXON_BEARING_MODEL_DIR = "ml/artifacts/bearing/rf-v1"
   python edge/lora_gateway.py --port /dev/serial0
   ```

The Raspberry Pi captures a compatible local vibration window, supplies its
`asset_id`, `component_id`, numeric `signal`, and `sampling_frequency_hz` to
`edge.bearing_inference.diagnose_payload`, then queues the resulting compact
diagnostic through `edge.lora_pi_sender`. The expected window length and
frequency are read from the bundle; incompatible inputs yield
`SENSOR_DATA_INVALID`, never a normal result. Raw 64 kHz vibration samples are
never transmitted over LoRa.

## Dashboard data path

The dashboard's primary bearing workflow does not require a file upload. A
Raspberry Pi local inference sends each compact diagnostic summary through the
transparent-UART LoRa radio. The gateway validates and forwards it to the API;
the bearing workspace refreshes from the newest event for the selected asset
and shows the reported `component_id`.

The **Manual CSV replay** section is deliberately optional. It is for replaying
a recorded, contract-compatible vibration window during troubleshooting or a
demo when an edge device is unavailable. CSV replay events are tagged
`manual_csv_replay`; LoRa gateway events are tagged `lora_uart`, so operators can
distinguish the source of every result.

The **Paderborn data replay** workspace is the primary interactive demo path.
It reads the local prepared manifest and the corresponding raw MATLAB recording
only after the operator chooses a fact-sheet-labelled bearing, recording, and
window. The API derives the same 16 features and model decision used on the Pi,
returns a downsampled waveform only for display, and saves the outcome as
`paderborn_dataset_replay` with `simulated: true`. The displayed documented
dataset condition and model decision are intentionally separate: a historical
laboratory replay is not a live LoRa event or a confirmation of field-machine
condition.

## Evidence and safety boundaries

- No Paderborn files or trained bearing-model bundle are committed to this
  repository. Until a locally acquired, fact-sheet-labelled dataset has been
  trained, AXON reports the bearing model as unavailable rather than inventing
  model metrics, class counts, or fault claims.
- Synthetic-development results cannot be used to support bearing-location
  claims.
- Classifier probabilities are marked uncalibrated. `FAULT_SUSPECTED` remains
  a hypothesis pending equipment-specific inspection.
- `config/repair_documents.example.json` and
  `config/pricing_catalogue.example.json` are intentionally empty. AXON returns
  unavailable/incomplete states until an authorized manual or verified price is
  supplied. It does not infer part compatibility, procedures, or prices.
- The edge journal is bounded to 1,000 events by default. It is local evidence
  storage, not a safety-certified queue or a substitute for a database.

## APIs

- `GET /diagnostics/taxonomy`
- `GET /diagnostics/model-status`
- `POST /diagnostics/infer`
- `GET /diagnostics/history?asset_id=<id>`
- `POST /diagnostics/technician-confirmation`
- `GET /repair-documents/search?query=<terms>`
- `POST /cost-estimates`

`/cost-estimates` only totals supplied numeric line items. A missing unit price
or labour input returns an incomplete estimate and never a fabricated total.
