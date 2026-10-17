"""Prepare the real-world UCI MetroPT-3 compressor telemetry for Axon.

The source CSV is intentionally not versioned.  It is a 208 MB CC BY 4.0
dataset from UCI; this module converts it in chunks and records only the
derived, reproducible training table locally.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


SOURCE_URL = "https://doi.org/10.24432/C5VW3R"
SOURCE_CITATION = "Davari et al. (2021), UCI MetroPT-3 Dataset, CC BY 4.0"
RAW_COLUMNS = ("timestamp", "TP2", "Oil_temperature", "Motor_current")
FEATURES = ("pressure", "oil_temperature", "motor_current")

# Operator-reported failure windows published with the UCI record.  The raw
# file itself is unlabelled, so labels are explicitly derived from these
# documented windows rather than inferred from future values.
FAILURE_WINDOWS = (
    ("2020-04-18 00:00:00+00:00", "2020-04-18 23:59:59+00:00"),
    ("2020-05-29 23:30:00+00:00", "2020-05-30 06:00:00+00:00"),
    ("2020-06-05 10:00:00+00:00", "2020-06-07 14:30:00+00:00"),
    ("2020-07-15 14:30:00+00:00", "2020-07-15 19:00:00+00:00"),
)


def _label_failure_windows(timestamps: pd.Series) -> pd.Series:
    labels = pd.Series(False, index=timestamps.index)
    for start, end in FAILURE_WINDOWS:
        labels |= timestamps.between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")
    return labels.astype(int)


def prepare(raw_path: Path, output_path: Path, chunksize: int = 100_000) -> int:
    """Stream the source CSV into Axon's explicit MetroPT-3 feature schema."""
    raw_path, output_path = Path(raw_path), Path(output_path)
    if not raw_path.is_file():
        raise FileNotFoundError(f"MetroPT-3 source CSV was not found: {raw_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing prepared dataset: {output_path}")

    rows_written = 0
    for chunk in pd.read_csv(raw_path, usecols=list(RAW_COLUMNS), chunksize=chunksize):
        converted = pd.DataFrame(
            {
                "ts": pd.to_datetime(chunk["timestamp"], utc=True, errors="raise"),
                "machine_id": "MetroPT3-APU",
                "pressure": pd.to_numeric(chunk["TP2"], errors="raise"),
                "oil_temperature": pd.to_numeric(chunk["Oil_temperature"], errors="raise"),
                "motor_current": pd.to_numeric(chunk["Motor_current"], errors="raise"),
            }
        )
        converted["label"] = _label_failure_windows(converted["ts"])
        converted.to_csv(output_path, mode="a", index=False, header=rows_written == 0)
        rows_written += len(converted)
    return rows_written


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare UCI MetroPT-3 for Axon training")
    parser.add_argument("--input", type=Path, required=True, help="MetroPT3(AirCompressor).csv from UCI")
    parser.add_argument("--output", type=Path, default=Path("ml/data/metropt3/metropt3_prepared.csv"))
    parser.add_argument("--chunksize", type=int, default=100_000)
    args = parser.parse_args()
    print(f"prepared {prepare(args.input, args.output, args.chunksize)} MetroPT-3 rows at {args.output}")


if __name__ == "__main__":
    main()
