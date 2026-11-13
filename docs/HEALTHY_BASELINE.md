# Healthy-only baseline

Small factories have no record of past failures, so a detector cannot be trained on fault examples from the machine it watches. The baseline is fitted only on windows recorded while a machine runs normally and flags windows that differ from them.

## How it works

1. Each window is reduced to the 16 engineered features in `ml/bearing/signal.py`, the same ones the supervised classifier uses.
2. Features are scaled by the healthy windows' median and median absolute deviation, so a few odd windows during recording do not distort the scale.
3. An Isolation Forest (Liu, Ting and Zhou, 2008) is fitted on the scaled healthy windows.
4. The last fifth of the healthy windows is held back from fitting. The alarm threshold is the anomaly score that the chosen share of them (1% by default) would exceed.
5. For a new window the baseline returns a drift score, the threshold, whether it drifted, and the three features that moved furthest from normal with their direction.

A baseline belongs to one machine and one sensor mounting. It reports "changed from this machine's normal". It does not name a fault or predict a failure date.

## Fitting one

At least 40 healthy windows are required. From a prepared dataset (`python -m ml.data.paderborn` output), using one healthy physical bearing as the machine:

~~~powershell
python -m ml.bearing.baseline --prepared ml/data/paderborn/prepared/prepared.npz --group K001 --asset-id demo-motor-001 --evaluate
~~~

This writes `baseline.joblib` and `metadata.json` to `ml/artifacts/bearing/baselines/demo-motor-001/`. With `--evaluate` it also scores every other bearing in the dataset and writes `evaluation.json`. The command refuses a group that is not labelled healthy.

Fitted baselines are per machine and are not committed to the repository.

## Using it on the edge

`edge.bearing_runner` looks for a baseline in `--baseline-dir`, then `AXON_BASELINE_DIR`, then `ml/artifacts/bearing/baselines/<asset-id>`, and prints which detector it is using at start-up.

- **Baseline found:** it is the primary detector. A drifted window is sent as `FAULT_SUSPECTED`. The supervised classifier, if deployed, only adds a secondary hint about the kind of damage; when it gives no fault hint, the fault class is `unknown`. Confidence is left empty because an anomaly score is not a probability.
- **No baseline:** the supervised classifier decides alone, as before.

The LoRa v2 frame is unchanged. The baseline's version travels in the model-version field, and the full comparison (drift score, threshold, changed features) stays in the Pi journal and in the diagnostic evidence when the result is posted directly.

Loading checks the artifact's SHA-256, the feature order, the input contract and the scikit-learn version, as the classifier bundle does.

## What is and is not verified

- Verified by `tests/test_baseline.py` on synthetic signals: fitting without fault labels, flagging windows with periodic impacts, the minimum-window rule, integrity checks, and the edge and LoRa path.
- Not verified: performance on the Paderborn recordings or on a real machine. The repository packages only eight demo windows, too few to fit a baseline, so no detection or false-alarm figures are claimed.
- Expected limitation: a baseline fitted on one bearing will often flag a different healthy bearing, because their normal differs. The evaluation report lists other healthy bearings separately for that reason.

## Feedback from the technician

When a technician closes a repair proposal, the finding is stored with a baseline action: treat the flagged windows as normal after a false alarm, keep them as a fault example after a confirmed fault, or record healthy running again after a repair. The action is recorded for a person to carry out; the baseline is not refitted automatically.
