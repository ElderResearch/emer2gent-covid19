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

Mobility data is updated weekly into a global cvs. The data contains;
- country_region_code
- country_region
- date
- sub_region_1
- sub_region_2
- country_region_code
- retail_and_recreation_percent_change_from_baseline
- grocery_and_pharmacy_percent_change_from_baseline
- parks_percent_change_from_baseline
- transit_stations_percent_change_from_baseline
- workplaces_percent_change_from_baseline
- residential_percent_change_from_baseline

The script will filter down to US only mobility data 
Further more it join the Federal Information Processing (fip) 
at a state & county level.

Note: 
This script depends on the data/fips.csv being scraped 
Run script from the root of the Repo. 

"""


# ------- Functions ------- #


def get_google_mobility():
    """
    Download Google's global mobility data directly from URL 
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
    mobility_file = data_dir / "intermediate" / "US_mobility_data.csv"
    if not mobility_file.exists():
        print("getting data")
        logging.info(f"{mobility_file} does not exist.")
        mobility_raw = get_google_mobility()
        US_mobility_df = mobility_raw[mobility_raw.country_region == "United States"]
        US_mobility_df.reset_index(inplace=True, drop=True)

        # Columns renamed for consistency across tables
        # Drop "percent_change_from_baseline" suffix for more compact representation in ABT
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

        # District of Columbia we assume to be a county
        US_mobility_df.loc[
            US_mobility_df.state == "District of Columbia", "county"
        ] = "District of Columbia"

        # Drop Columns that are constant over all timestamps 
        del US_mobility_df["country"]
        del US_mobility_df["country_region"]

        # Import and join fips.csv to US_mobility
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
