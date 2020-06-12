"""Data management."""

import pathlib
import requests

# placing this first to avoid circular imports
DATA_DIR = pathlib.Path(__file__).resolve().parents[5] / "data"

from trent.data import census, cdc_health  # noqa: F401, E402


def get_covidtracking_data() -> None:
    url = "https://covidtracking.com/api/v1/states/daily.csv"

    r = requests.get(url)
    r.raise_for_status()

    outfile = DATA_DIR / "raw" / "covidtracking.csv"
    outfile.write_text(r.content.decode(r.encoding))


def run_pipeline() -> None:
    get_covidtracking_data()
    cdc_health.download_cdc_data()
    cdc_health.transform_cdc_data()
