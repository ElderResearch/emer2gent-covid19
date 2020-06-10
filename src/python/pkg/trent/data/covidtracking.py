#!/usr/bin/env python3

import requests
from pathlib import Path


def get_covidtracking_data():
    url = "https://covidtracking.com/api/v1/states/daily.csv"

    r = requests.get(url)
    r.raise_for_status()

    outfile = Path(__file__).resolve().parents[5] / "data" / "covidtracking.csv"
    outfile.write_text(r.content.decode(r.encoding))


if __name__ == "__main__":
    get_covidtracking_data()
