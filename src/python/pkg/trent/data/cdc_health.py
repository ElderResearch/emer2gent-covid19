#!/usr/bin/env python3

import pandas as pd
import requests
import logging

from trent.data import DATA_DIR


def download_cdc_data() -> None:
    infection_url = "https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_confirmed_usafacts.csv"
    infection_file_path = DATA_DIR / "raw" / "covid_confirmed_usafacts.csv"

    logging.info("Downloading covid_confirmed_usafacts.csv")
    r = requests.get(infection_url)
    r.raise_for_status()

    logging.info(f"Writing covid_confirmed_usafacts.csv to {infection_file_path}")
    infection_file_path.parent.mkdir(exist_ok=True, parents=True)
    infection_file_path.write_text(r.content.decode("utf-8"))

    deaths_url = "https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_deaths_usafacts.csv"
    deaths_file_path = DATA_DIR / "raw" / "covid_deaths_usafacts.csv"

    logging.info("Downloading covid_deaths_usafacts.csv")
    r = requests.get(deaths_url)
    r.raise_for_status()

    logging.info(f"Writing covid_deaths_usafacts.csv to {deaths_file_path}")
    deaths_file_path.write_text(r.content.decode("utf-8"))


def transform_cdc_data() -> None:
    """
    Tranform CDC to common format compatible with the analytical base table.

    The Centers for Disease Control and Prevention Raw scraped data
    - covid_deaths_usafacts.csv
    - covid_confirmed_usafacts.csv

    has the following long-table format:

    countyFIPS | County Name| State	| stateFIPS	| 1/22/20 | 1/23/20 | 1/24/20	...
        ...    |   ...      |  ...   |  ...     | ....    |  ...    | ...


    The script will map the data into the following format:

    deaths | date    |  county	| fips_code | state_code | confirmed
    ...    | 1/22/20 |  ...     | ....      | ...        | ...
    """

    deaths_file_path = DATA_DIR / "raw" / "covid_deaths_usafacts.csv"
    infection_file_path = DATA_DIR / "raw" / "covid_confirmed_usafacts.csv"

    CDC_deaths = pd.read_csv(deaths_file_path)
    CDC_confirmed = pd.read_csv(infection_file_path)

    # Columns renamed for consistency with downstream tables
    CDC_deaths.rename(
        inplace=True,
        columns={
            "countyFIPS": "county_fip",
            "County Name": "county",
            "State": "state_code",
        },
    )

    CDC_confirmed.rename(
        inplace=True,
        columns={
            "countyFIPS": "county_fip",
            "County Name": "county",
            "State": "state_code",
        },
    )

    CDC_deaths.drop(columns=["stateFIPS"], inplace=True)
    CDC_confirmed.drop(columns=["stateFIPS"], inplace=True)

    # Handle cases: Statewide Unallocated -> missing county data for given states
    # we thus do not have fips for such cases and so no data is present in other fields.
    CDC_deaths = CDC_deaths[~(CDC_deaths["county"] == "Statewide Unallocated")]
    CDC_confirmed = CDC_confirmed[~(CDC_confirmed["county"] == "Statewide Unallocated")]

    # New york city is present in data -> county name is new york county ->
    # this is not a county thus has no fip's
    CDC_deaths = CDC_deaths[
        ~(CDC_deaths["county"] == "New York City Unallocated/Probable")
    ]
    CDC_confirmed = CDC_confirmed[
        ~(CDC_confirmed["county"] == "New York City Unallocated/Probable")
    ]

    # Further edge cases that are removed using the same reasoning above (Alaska)
    CDC_deaths = CDC_deaths[~(CDC_deaths.county == "Wade Hampton Census Area")]
    CDC_confirmed = CDC_confirmed[~(CDC_confirmed.county == "Wade Hampton Census Area")]

    CDC_deaths = CDC_deaths[~(CDC_deaths.county == "Grand Princess Cruise Ship")]
    CDC_confirmed = CDC_confirmed[
        ~(CDC_confirmed.county == "Grand Princess Cruise Ship")
    ]

    # melt data into the required long format
    CDC_deaths_df = CDC_deaths.melt(
        id_vars=["county_fip", "county", "state_code"],
        var_name="date",
        value_name="deaths",
    )
    CDC_confirmed_df = CDC_confirmed.melt(
        id_vars=["county_fip", "county", "state_code"],
        var_name="date",
        value_name="confirmed",
    )

    # By construction both tables should match up perfectly
    # Add confirmed column to final data frame
    CDC_full_df = CDC_deaths_df.copy()
    if all(CDC_confirmed_df.date == CDC_deaths_df.date) & all(
        CDC_confirmed_df.county_fip == CDC_deaths_df.county_fip
    ):
        CDC_full_df["confirmed"] = CDC_confirmed_df["confirmed"]
        logging.info("CDC joined")
    else:
        logging.info("CDC data not joined")

    # Reorder columns:
    new_column_order = [
        "date",
        "county_fip",
        "state_code",
        "county",
        "deaths",
        "confirmed",
    ]
    CDC_full_df = CDC_full_df.loc[:, new_column_order]
    CDC_full_df["date"] = pd.to_datetime(CDC_full_df["date"])

    # Export: create intermediate data directory if it doesn't exist
    intermediate_dir = DATA_DIR / "intermediate"
    intermediate_dir.mkdir(exist_ok=True)

    # write CDC_full_df to csv
    CDC_full_df.to_csv(intermediate_dir / "CDC_full_data.csv", index=False)


if __name__ == "__main__":
    download_cdc_data()
    transform_cdc_data()
