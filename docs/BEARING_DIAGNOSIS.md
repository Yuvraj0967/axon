# Bearing diagnosis extension

## What is implemented

AXON now has a bearing-vibration path that is deliberately separate from the
existing synthetic and MetroPT-3 compressor paths. It has a versioned taxonomy,
strict sampling/window validation, shared engineered features, group-aware
Random Forest training, an optional compact TensorFlow 1D CNN trainer, validated
Random Forest bundle loading, edge MQTT inference, API diagnostic records, and
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
   than labelled as healthy.

   ```powershell
   python -m ml.data.prepare --config path/to/paderborn.local.json
   ```

4. Train the CPU-friendly reference model with independent recording groups:

   ```powershell
   python -m ml.training.train_random_forest --prepared ml/data/paderborn/prepared/windows.npz --output ml/artifacts/bearing/rf-v1
   ```

5. Optionally train the 1D CNN on a TensorFlow-supported training host:

   ```powershell
   python -m ml.training.train_cnn --prepared ml/data/paderborn/prepared/windows.npz --output ml/artifacts/bearing/cnn-v1
   ```

   The CNN command honestly fails with an install instruction when TensorFlow
   is absent; it does not substitute a different model or claim an ONNX export.

6. Point the edge and backend at a checksum-validated Random Forest bundle and
   run the dedicated edge process:

   ```powershell
   $env:AXON_BEARING_MODEL_DIR = "ml/artifacts/bearing/rf-v1"
   python edge/bearing_inference.py
   ```

Send a JSON payload with `asset_id`, `component_id`, numeric `signal`, and
`sampling_frequency_hz` to `factory/<asset>/bearing-vibration`. The expected
window length and frequency are read from the bundle; incompatible inputs yield
`SENSOR_DATA_INVALID`, never a normal result.

## Evidence and safety boundaries

- No Paderborn files were present in this checkout, so there are no real
  Paderborn model metrics, class counts, selected model, or fault claims.
- Existing MetroPT-3 and synthetic results remain separate and cannot be used
  to support bearing-location claims.
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
