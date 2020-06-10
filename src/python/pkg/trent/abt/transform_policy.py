#!/usr/bin/env python3
import os
from datetime import datetime

import numpy as np
import pandas as pd

"""
Overview:

Raw data - Public Health England Summary Stats US States
- Contains US state-level Policy data & county-level data for specific counties
- Each row is an observation of a state/county with information on policy start 
and end dates.

Transform data - In this script we transform the data into a format consistent with the 
analytical base table.

The transformed data contains the folowing columns:
- Date (Daily matching the CDC data)
- state_fip  = state fips code
- county_fip = county fips (missing if we only have state level data)
- state_code  = state code eg. AL = Alabama
- state = state name
- county = county name (missing if we only have state level data)

Policy features indicating if a policy was in place at the timestamp.
Note if None Issued then the policy was not implemented. The policies considered are named: 
- travel_limit
- stay_home
- educational_fac
- phase_1
- phase_2
- phase_3

Note: 
Public health England data consists of state and county-level policy data.

"""

# ------- Functions ------- #


def get_policy_ABT(Policy_df, CDC_df):

    """
    Construct ABT for the policy data 

    Args:
        Policy_df: Raw policy data
        CDC_DF:  Intermediate CDC data (we require the timestamp)

    Returns:
        - ABT with structure explained in overview
    """

    # Build ABT for each state or county individually 
    # concatenate to create final data 
    list_of_df = []
    n_rows = len(Policy_df)

    for i in range(n_rows):
        # Check if a county is present in the data
        county_present = type(Policy_df.county_name.iloc[i]) == str
        # If true -> county is present O.W. only State level policy data 

        if county_present:
            # county level ABT construction 
            sub_df = state_policy_abt(
                state_idx=i, state_level=False, Policy_df=Policy_df, CDC_df=CDC_df
            )
        else:
            # state level ABT construction
            sub_df = state_policy_abt(
                state_idx=i, state_level=True, Policy_df=Policy_df, CDC_df=CDC_df
            )

        list_of_df.append(sub_df)
    # Join data by row into one ABT
    Policy_ABT = pd.concat(list_of_df, ignore_index=True)

    return Policy_ABT


def state_policy_abt(state_idx, state_level, Policy_df, CDC_df):
    
    """ Construct ABT for individual states or county from the policy data
     Args:
        state_idx : index of state in Policy_df
        state_level: True = state case & False = county case
        Policy_df: Raw policy data
        CDC_DF: Intermediate CDC data (we require the time stamp)
    Returns:
        - ABT for state/county level in the structure explained in overview
    """

    # Get the states name for a given index 
    state_name = Policy_df.state_name.iloc[state_idx]

    # STEP 1: Construct a dataframe with rows coresponding to CDC timestamp
    state_df = pd.DataFrame(CDC_df.date.unique())
    state_df.columns = ["date"]

    # ADD aditional information to dataframe that depends on state or county 
    if state_level:
        # if we only have state info
        state_df["state_fip"] = Policy_df.fips_code.iloc[state_idx]
        state_df["county_fip"] = np.NaN 
        state_df["state"] = state_name
        state_df["county"] = np.NaN 
    else:
        # if we have county info
        state_df["state_fip"] = np.NaN
        state_df["county_fip"] = Policy_df.fips_code.iloc[state_idx]
        state_df["state"] = state_name
        state_df["county"] = Policy_df.county_name.iloc[state_idx]

    # STEP2: Get columns for policies with consistent name pairs
    # eg. "travel_limit_start_date" & "travel_limit_end_date" 
    col_names = [
        "travel_limit",
        "stay_home",
        "educational_fac",
    ]

    # Loop over each column to extract the policy featuer for the dataframe timestamp
    for k in col_names:

        # Get start & end date of policy:
        start_date = Policy_df.loc[state_idx, f"{k}_start_date"]
        end_date = Policy_df.loc[state_idx, f"{k}_end_date"]

        # Run to get policy column & add to dataframe
        new_col = get_policy_col(start_date, end_date, date=state_df.date)
        state_df[k] = new_col

    # STEP3: Repeat the same steps but for the the following column pairs: 
    # The folwing columns can be treated as state & end dates for phase 1,2 & 3 
    col_name_pairs = [
        ["all_non-ess_business_start_date", "phase_1_reopen_date"],
        ["any_business_start_date", "phase_2_reopen_date"],
        ["any_gathering_restrict_start_date", "phase_3_reopen_end_date"],
    ]

    # Same-steps as before: 
    for i, k in enumerate(col_name_pairs):

        col_start = k[0]
        col_end = k[1]

        start_date = Policy_df.loc[state_idx, col_start]
        end_date = Policy_df.loc[state_idx, col_end]

        # Phase_i columns naming conventions for i=1,2,3
        new_col_name = f"phase_{i+1}"
        new_col = get_policy_col(start_date, end_date, date=state_df.date)
        state_df[new_col_name] = new_col

    return state_df


def get_policy_col(start_date, end_date, date):
    
    """ Gets Policy features for a policy specified by its start and end date
     Args:
        start_date : start date of policy (timestamp or None Issued)
        end_date: end date of policy (timestamp or None Issued )
        date: list/array of timestamp to check policy against 
    Returns:
        - binary column of 0's and 1's to say if a policy was present at
        each timestamp in the date imput
        -'None Issued' if policy was not issued 
    """

    # Check if the policy started: 
    if start_date == "None Issued":
        # Policy did not start 
        return start_date

    else:
        # Policy exisits; 1 = Policy in place & 0 = Not inplace 
        if end_date == "None Issued":
            # policy started but is still on going
            return (date >= start_date) * 1
        else:
            # Policy started & ended 
            bool_vals = (date >= start_date) & (date <= end_date)
            return bool_vals * 1


if __name__ == "__main__":

    # Import data: England Health data 
    path_policy = os.path.abspath(
        "data/Public Health England Summary Stats US States.xlsx"
    )
    Policy_df = pd.read_excel(path_policy)

    # CDC data requiered for time stamp -> this is our left join in the ABT 
    CDC_path = os.path.abspath("data/intermediate/CDC_full_data.csv")
    if os.path.exists(CDC_path):
        CDC_df = pd.read_csv(CDC_path)
        CDC_df["date"] = CDC_df.date.apply(lambda x: datetime.strptime(x, "%Y-%m-%d"))
    else:
        exit()

    # import fips data 
    fips_abs_path = os.path.abspath("data/fips.csv")
    fips_df = pd.read_csv(fips_abs_path)

    # Get Policy ABT
    Policy_ABT = get_policy_ABT(Policy_df=Policy_df, CDC_df=CDC_df)

    # Left join for state codes:
    fips_states = fips_df[["state", "state_code"]].drop_duplicates()
    Policy_ABT = pd.merge(
        Policy_ABT, fips_states, how="left", left_on=["state"], right_on=["state"]
    )

    # Column order:
    new_column_order = [
        "date",
        "state_fip",
        "county_fip",
        "state_code",
        "state",
        "county",
        "travel_limit",
        "stay_home",
        "educational_fac",
        "phase_1",
        "phase_2",
        "phase_3",
    ]
    Policy_ABT = Policy_ABT.loc[:, new_column_order]

    # Export: Check that intermediate directory folder exisits O.W create
    check_directory = os.path.abspath("data/intermediate")
    if not os.path.exists(check_directory):
        os.makedirs(check_directory)

    # Export CDC_full_df to csv
    file_name = "Policy_ABT.csv"
    Policy_ABT.to_csv(f"{check_directory}/{file_name}", index=False)
