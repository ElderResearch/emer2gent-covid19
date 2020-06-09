#!/usr/bin/env python3
import io
import logging
from pathlib import Path

import pandas as pd
import requests

pd.options.mode.chained_assignment = None

logging.basicConfig(level=logging.INFO)

"""
Overview:

Extract Google Mobility data for US at a county level
url: https://www.google.com/covid19/mobility/

Mobility data updated weekly in global cvs. The data contains;
- sub_region_1
- sub_region_2
- country_region_code
- retail_and_recreation_percent_change_from_baseline
- grocery_and_pharmacy_percent_change_from_baseline
- parks_percent_change_from_baseline
- transit_stations_percent_change_from_baseline
- workplaces_percent_change_from_baseline
- residential_percent_change_from_baseline

We will filter for US & add the Federal Information Processing
Standards (FIPS) on a county level
- FIPS mapping can be found @ data/fips.csv from repo. root
"""


# ------- Functions ------- #


def get_google_mobility():
    """
    Download Google's global mobility data
    """
    url = "https://www.gstatic.com/covid19/mobility/Global_Mobility_Report.csv"
    logging.info("Downloading Google mobility data")

    # request csv & load to pandas dataFrame
    r = requests.get(url)
    r.raise_for_status()
    logging.info("Download complete")

    return pd.read_csv(
        io.StringIO(r.content.decode("utf-8")), low_memory=False, parse_dates=["date"]
    )


if __name__ == "__main__":

    # Import global google mobility data & filter for US
    data_dir = Path(__file__).resolve().parents[5] / "data"
    mobility_file = data_dir / "US_mobility_data.csv"
    if not mobility_file.exists():
        logging.info(f"{mobility_file} does not exist.")
        mobility_raw = get_google_mobility()
        US_mobility_df = mobility_raw[mobility_raw.country_region == "United States"]
        US_mobility_df.reset_index(inplace=True, drop=True)

        # Columns renamed for consistency across tables unique identifying keys
        # Drop "percent_change_from_baseline" suffix for more compact representation
        US_mobility_df.rename(
            inplace=True,
            columns={
                "sub_region_1": "state",
                "sub_region_2": "county",
                "country_region_code": "country",
                "retail_and_recreation_percent_change_from_baseline": "retail_and_recreation",
                "grocery_and_pharmacy_percent_change_from_baseline": "grocery_and_pharmacy",
                "parks_percent_change_from_baseline": "parks",
                "transit_stations_percent_change_from_baseline": "transit_stations",
                "workplaces_percent_change_from_baseline": "workplaces",
                "residential_percent_change_from_baseline": "residential",
            },
        )

        # District of Columbia can be assumed as a county -> replace missing county
        # entry with 'state' name
        US_mobility_df.loc[
            US_mobility_df.state == "District of Columbia", "county"
        ] = "District of Columbia"

        # Drop Columns that are redundent
        del US_mobility_df["country"]
        del US_mobility_df["country_region"]

        # Import and join fips.csv to US_mobility -> this is one of our unique keys
        # fips.csv exists in data folder created by src/python/init_project.py
        fips_file = data_dir / "fips.csv"
        fips_df = pd.read_csv(fips_file)
        logging.info("Joining mobility data to FIPS data")
        US_mobility_df = pd.merge(
            US_mobility_df,
            fips_df,
            how="left",
            left_on=["state", "county"],
            right_on=["state", "county"],
        )

        # Filter: Drop the missing values in state & county - we cant identify their
        # fips code on all levels
        US_mobility_df = US_mobility_df[~US_mobility_df.state.isna()]
        US_mobility_df = US_mobility_df[~US_mobility_df.county.isna()]

        # Export US_mobility_df to csv
        US_mobility_df.to_csv(mobility_file, index=False)
        logging.info(f"Mobility data written to {mobility_file}")
