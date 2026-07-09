"""Download the M5 Forecasting - Accuracy dataset from Kaggle into data/raw/.

Requires Kaggle API credentials (see data/README.md): either
~/.kaggle/kaggle.json, or KAGGLE_USERNAME + KAGGLE_KEY in the environment.
Also requires accepting the competition rules on the Kaggle website once
(Kaggle blocks API downloads for competitions you haven't joined).

Usage:
    uv run python -m retail_demand.data_engineering.download_m5
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from retail_demand.config import DATA_RAW_DIR

COMPETITION = "m5-forecasting-accuracy"

EXPECTED_FILES = [
    "sales_train_validation.csv",
    "calendar.csv",
    "sell_prices.csv",
]


def download(dest_dir: Path = DATA_RAW_DIR) -> None:
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        raise SystemExit(
            "The 'kaggle' package is required: uv sync --extra data"
        ) from exc

    dest_dir.mkdir(parents=True, exist_ok=True)

    api = KaggleApi()
    api.authenticate()

    print(f"Downloading {COMPETITION} to {dest_dir} ...")
    api.competition_download_files(COMPETITION, path=str(dest_dir), quiet=False)

    zip_path = dest_dir / f"{COMPETITION}.zip"
    if zip_path.exists():
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest_dir)
        zip_path.unlink()

    missing = [f for f in EXPECTED_FILES if not (dest_dir / f).exists()]
    if missing:
        raise SystemExit(f"Download finished but missing expected files: {missing}")

    print(f"Done. Files present: {EXPECTED_FILES}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default=str(DATA_RAW_DIR), help="Destination directory.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    download(Path(args.dest))
