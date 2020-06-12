#!/usr/bin/env python3

import requests

from trent.data import DATA_DIR


def get_covidtracking_data():
    url = "https://covidtracking.com/api/v1/states/daily.csv"

    r = requests.get(url)
    r.raise_for_status()

    outfile = DATA_DIR / "raw" / "covidtracking.csv"
    outfile.write_text(r.content.decode(r.encoding))


if __name__ == "__main__":
    get_covidtracking_data()
