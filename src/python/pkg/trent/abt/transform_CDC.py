#!/usr/bin/env python3
from pathlib import Path

import pandas as pd

"""
Overview: Tranform CDC to common cross sectional format

Centers for Disease Control and Prevention Raw scraped data
- covid_deaths_usafacts.csv
- covid_confirmed_usafacts.csv

Current Raw format

countyFIPS | County Name| State	| stateFIPS	| 1/22/20 | 1/23/20 | 1/24/20	...
    ...    |   ...      |  ...   |  ...     | ....    |  ...    | ...

- Table for where rows are entire observations

Output format

deaths | date    |  county	| fips_code | state_code | confirmed
...    | 1/22/20 |  ...     | ....      | ...        | ...

"""

data_dir = Path(__file__).resolve().parents[5] / "data"

# Import data
deaths_file = data_dir / "covid_deaths_usafacts.csv"
confirmed_file = data_dir / "covid_confirmed_usafacts.csv"
CDC_deaths = pd.read_csv(deaths_file)
CDC_confirmed = pd.read_csv(confirmed_file)

# Columns renamed for consistency across tables unique identifying keys
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

# Handle cases: Statewide Unallocated -> CDC has missing county level data
# Despite having policy data present we will not have data in any other fields
# eg. weather, ACS and so we have droped these cases
CDC_deaths = CDC_deaths[~(CDC_deaths["county"] == "Statewide Unallocated")]
CDC_confirmed = CDC_confirmed[~(CDC_confirmed["county"] == "Statewide Unallocated")]

# New york city is present in data -> county name is new york county ->
# remove the below as we dont have fips
CDC_deaths = CDC_deaths[~(CDC_deaths["county"] == "New York City Unallocated/Probable")]
CDC_confirmed = CDC_confirmed[
    ~(CDC_confirmed["county"] == "New York City Unallocated/Probable")
]

# Further edge cases: (no fips and not states)
CDC_deaths = CDC_deaths[~(CDC_deaths.county == "Wade Hampton Census Area")]
CDC_confirmed = CDC_confirmed[~(CDC_confirmed.county == "Wade Hampton Census Area")]

CDC_deaths = CDC_deaths[~(CDC_deaths.county == "Grand Princess Cruise Ship")]
CDC_confirmed = CDC_confirmed[~(CDC_confirmed.county == "Grand Princess Cruise Ship")]

# Get cross sectional form
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

# By construction both tables match up perfectly
# Add confirmed column to final data frame
CDC_full_df = CDC_deaths_df.copy()
if all(CDC_confirmed_df.date == CDC_deaths_df.date) & all(
    CDC_confirmed_df.county_fip == CDC_deaths_df.county_fip
):
    print("Adding confirmed cases -------------------")
    CDC_full_df["confirmed"] = CDC_confirmed_df["confirmed"]
else:
    print("Data not matched")

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

# Export: Check that intermediate data folder exisits O.W create
intermediate_dir = data_dir / "intermediate"
if not intermediate_dir.exists():
    intermediate_dir.mkdir()

# Export CDC_full_df to csv
CDC_full_df.to_csv(intermediate_dir / "CDC_full_data.csv", index=False)
