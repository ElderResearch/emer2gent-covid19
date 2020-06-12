"""Data management."""

import pathlib
from trent.data import census, cdc_health  # noqa: F401

DATA_DIR = pathlib.Path(__file__).resolve().parents[5] / "data"


def run_pipeline() -> None:
    cdc_health.download_cdc_data()
    cdc_health.transform_cdc_data()
