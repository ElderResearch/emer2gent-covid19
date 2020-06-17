#!/usr/bin/env python3
import pandas as pd
import os

from trent.data import DATA_DIR


""" Overview 

In this script we combine the following tables to construct a full ABT:
- CDC intermediate data (county level) 
- Policy intermediate data ( state level with county-level cases) 
- US mobility data (county level) 
- Weather data (county level)
- Department of Labour Unemployment data (county level) 
- ACS intermediate data (county level) 
- COVID tracking data (state level)
- US Land Area Data (county level) -> used to derive population density 

Note: 

- For the case of the Policy data, we assume that the county inherits the policy from
what the state polices. Apart from the cases where county-level policy data is present. 

- The data adds all raw columns that can be filtered down at a later point according to the modeling.

- The CDC data acts as our left table as this is the labeled data for any modeling. 

"""

# ------- Main Function ------- #


def join_all_data():

    # CDC = LEFT TABLE

    # STEP 1:
    # Join policy data to CDC data
    # Policy data is a combination of state level & county level data

    # Split into disjoin data sets bassed on county & state level existence in policy data
    Policy_state_df = Policy_df[Policy_df.county.isna()]
    Policy_county_df = Policy_df[~Policy_df.county.isna()]

    # checks to CDC data
    # ADD a check to scrip:
    county_names_with_policy = Policy_county_df.county.unique()
    county_names_in_cdc = CDC_df.county.unique()

    # Check if any of the policy names are not in the CDC!
    not_in_cdc = [k for k in county_names_with_policy if k not in county_names_in_cdc]
    print(f"County in Policy but not in CDC:\n {not_in_cdc}")
    # This is getting droped becasue of the left Join

    # Furthermore, split the CDC wrt the fips county code that exisit in policy data
    county_fip_with_policy = Policy_county_df.county_fip.unique()
    CDC_df_0 = CDC_df[
        ~CDC_df.county_fip.isin(county_fip_with_policy)
    ]  # without couty level data
    CDC_df_1 = CDC_df[
        CDC_df.county_fip.isin(county_fip_with_policy)
    ]  # with county level data

    # Join compodents sepretly:

    # Left join to CDC_df_0 -> this will give the state policy for counties
    ABT_sub_0 = pd.merge(
        CDC_df_0,
        Policy_state_df,
        how="left",
        left_on=["state_code", "date"],
        right_on=["state_code", "date"],
        suffixes=("", "_dropMe"),
    )

    print(f"ABT_SUB_0.shape = {ABT_sub_0.shape}")

    ABT_sub_0.drop(
        ABT_sub_0.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True
    )

    # left join on CDC_df_1 to add county level policy data
    ABT_sub_1 = pd.merge(
        CDC_df_1,
        Policy_county_df,
        how="left",
        left_on=["county_fip", "date"],
        right_on=["county_fip", "date"],
        suffixes=("", "_dropMe"),
    )
    ABT_sub_1.drop(
        ABT_sub_1.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True
    )
    print(f"ABT_SUB_1.shape = {ABT_sub_1.shape}")
    # Concat. row-wise to get version 0 of the ABT -> [CDC,policy ]
    ABT_V0 = pd.concat([ABT_sub_0, ABT_sub_1], ignore_index=True)
    print("Added Policy data:")
    print(f"ABT.shape ={ABT_V0.shape}")

    # -------------------------------------------------------------------------------

    # STEP 2: Add mobility data
    # Left join to ABT_V0 on [county_fip , date]
    ABT_V1 = pd.merge(
        ABT_V0,
        Mobility_df,
        how="left",
        left_on=["county_fip", "date"],
        right_on=["county_fip", "date"],
        suffixes=("", "_dropMe"),
    )
    ABT_V1.drop(ABT_V1.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True)

    print("Added Mobility data:")
    print(f"ABT.shape ={ABT_V1.shape}")

    # -------------------------------------------------------------------------------
    # STEP 3: Add weather data
    # Weather data can be joined [county_fip , date]
    ABT_V2 = pd.merge(
        ABT_V1,
        weather_df,
        how="left",
        left_on=["county_fip", "date"],
        right_on=["county_fip", "date"],
        suffixes=("", "_dropMe"),
    )
    ABT_V2.drop(ABT_V2.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True)
    print("Added Weather data:")
    print(f"ABT.shape ={ABT_V2.shape}")

    # -------------------------------------------------------------------------------
    # STEP 4: Add Census data
    # Census data is using state_fips as the prefix to the full fips AND county fips the suffix
    # We need to parse these from county_fip to do the join
    fips_id = ABT_V2.county_fip.apply(str)
    ABT_V2["state_fip"] = fips_id.apply(parse_state).apply(int)
    ABT_V2["proxy_fip"] = fips_id.apply(parse_county).apply(int)

    # JOIN left :
    ABT_V3 = pd.merge(
        ABT_V2,
        ACS_full_df,
        how="left",
        left_on=["state_fip", "proxy_fip"],
        right_on=["state_fips", "county_fips"],
        suffixes=("", "_dropMe"),
    )
    ABT_V3.drop(ABT_V3.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True)

    # drop proxy_fip & state fips & county fips
    ABT_V3 = ABT_V3.drop(["proxy_fip","Unnamed: 0"], axis=1, errors='ignore')

    print("Added Census data:")
    print(f"ABT.shape ={ABT_V3.shape}")

    # -------------------------------------------------------------------------------

    # STEP 5: Add Unemployment Data
    # Join on [county_fip, date]
    ABT_V4 = pd.merge(
        ABT_V3,
        DoL_df,
        how="left",
        left_on=["county_fip", "date"],
        right_on=["county_fip", "date"],
        suffixes=("", "_dropMe"),
    )
    ABT_V4.drop(ABT_V4.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True)
    print("Added Unemployment data:")
    print(f"ABT.shape ={ABT_V4.shape}")

    # -------------------------------------------------------------------------------

    # STEP 6 : Add Tracking data
    # Ensure columns have the same data type
    ABT_V4["date"] = pd.to_datetime(ABT_V4["date"].apply(str)).dt.date

    # Left join on state_fip and date in ABT_V4 to cov_fips and cov_date in tracking df
    ABT_V5 = pd.merge(
        ABT_V4,
        tracking_df,
        how="left",
        left_on=["state_fip", "date"],
        right_on=["cov_fips", "cov_date"],
        suffixes=("", "_dropMe"),
    )

    ABT_V5.drop(ABT_V5.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True)
    ABT_V5.drop(["cov_date", "cov_fips"], axis=1, inplace=True)

    print("Added Testing data:")
    print(f"ABT.shape ={ABT_V5.shape}")

    # -------------------------------------------------------------------------------

    # STEP 6: Add population density data 
    # time indp. -> join on county_fip 
    print(area_df.columns)
    ABT_V6 = pd.merge(
        ABT_V5,
        area_df,
        how="left",
        left_on=["county_fip"],
        right_on=["county_fip"],
        suffixes=("", "_dropMe")
    )

    ABT_V6.drop(ABT_V6.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True)
    ABT_V6.drop(["Areaname"],axis=1,inplace = True)
    # Get population density by total poluation / area mass -> zero divison returns nans 
    ABT_V6["pop_density"] = ABT_V6["acs_pop_total"]/ABT_V6["land_area"]

    print("Added Population Density:")
    print(f"ABT.shape ={ABT_V6.shape}")

    return ABT_V6


# ------- Helper Functions ------- #
# county_fip is composed of state fips & county fips
# if county_fip is 4 numbers (ABCD) then -> state fip is A & county_fips is BCD
# if county_fip is 5 numbers (ABCDE) the -> state fip is AB & county_fips is CDE
def parse_state(county_fips):
    # Get state fips(prefix)
    len_fip = len(county_fips)
    if len_fip == 1:
        # Missing
        return -1
    if len_fip == 4:
        return county_fips[0]
    if len_fip == 5:
        return county_fips[0:2]


def parse_county(county_fips):
    # get county_fips(suffix)
    len_fip = len(county_fips)
    if len_fip == 1:
        # missing
        return -1
    if len_fip == 4:
        return county_fips[1:]
    if len_fip == 5:
        return county_fips[2:]


if __name__ == "__main__":

    # Import data:
    intermediate_directory = DATA_DIR / "intermediate"

    # CDC Data
    file_name = "CDC_full_data.csv"
    CDC_df = pd.read_csv(f"{intermediate_directory}/{file_name}")

    # Polic data
    file_name = "Policy_ABT.csv"
    Policy_df = pd.read_csv(f"{intermediate_directory}/{file_name}")

    # Mobility data
    file_name = "US_mobility_data.csv"
    Mobility_df = pd.read_csv(f"{intermediate_directory}/{file_name}")
    # Weather data
    file_name = "weather_by_county_fips.csv"
    weather_df = pd.read_csv(f"{DATA_DIR}/{file_name}", error_bad_lines=False)

    # Census data
    file_name = "ACS_full.csv"
    ACS_full_df = pd.read_csv(f"{intermediate_directory}/{file_name}")

    # Uneployment data
    file_name = "DoL_daily_county.csv"
    DoL_df = pd.read_csv(f"{DATA_DIR}/{file_name}", error_bad_lines=False)

    # Clean uneployment:
    DoL_df.rename(
        inplace=True,
        columns={"Date": "date", "County Name": "county", "State": "state"},
    )
    # Drop State Code -> already exists as state_code
    DoL_df = DoL_df.drop(["State Code"], axis=1, errors='ignore')

    # Import tracking data:
    tracking_df = pd.read_csv(DATA_DIR / "covidtracking.csv")
    print(f"tracking_df.shape ={tracking_df.shape}")
    tracking_df.columns = [f"cov_{k}" for k in tracking_df.columns]
    tracking_df["cov_date"] = pd.to_datetime(tracking_df["cov_date"].apply(str)).dt.date

    keep = [
        "cov_date",
        "cov_fips",
        "cov_positive",
        "cov_negative",
        "cov_hospitalizedCurrently",
        "cov_total",
        "cov_totalTestResults",
    ]
    # filter keep columns from  tracking data :
    tracking_df = tracking_df.loc[:, tracking_df.columns.isin(keep)]

    # Get density data:
    area_df = pd.read_csv(DATA_DIR / "county_area.csv")

    # Get ABT
    ABT_final = join_all_data()

    # add daty of week feature (Monday is 0 ... Sunday is 6)
    ABT_final["day_of_week"] = pd.to_datetime(ABT_final["date"]).dt.dayofweek

    # Export Data
    PROCESSED_DIR = DATA_DIR / "processed"
    PROCESSED_DIR.mkdir(exist_ok=True)

    # Export CDC_full_df to csv
    ABT_final.to_csv(PROCESSED_DIR / "ABT_V1.csv", index=False)
