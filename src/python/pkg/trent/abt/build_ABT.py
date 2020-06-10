#!/usr/bin/env python3
import pandas as pd
import os


""" Overview 

In this script we combine the following tables to construct a full ABT; 
- CDC intermediate data ( county level ) 
- Policy intermediate data ( state level with county-level cases ) 
- US mobility data ( county level) 
- Weather data ( county level )
- Department of Labour Unemployment data ( county level ) 
- ACS intermediate data ( county level ) 

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

    ABT_sub_0.drop(
        ABT_sub_0.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True
    )

    # Inner join on CDC_df_1 to add county level policy data 
    ABT_sub_1 = pd.merge(
        CDC_df_1,
        Policy_county_df,
        how="inner",
        left_on=["county_fip", "date"],
        right_on=["county_fip", "date"],
        suffixes=("", "_dropMe"),
    )
    ABT_sub_1.drop(
        ABT_sub_1.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True
    )

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
    ABT_V1.drop(
        ABT_V1.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True
    )

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
    ABT_V2.drop(
        ABT_V2.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True
    )
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
    ABT_V3.drop(
        ABT_V3.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True
    )
   
    # drop proxy_fip & state fips & county fips
    del ABT_V3["proxy_fip"]
    del ABT_V3["Unnamed: 0"]
    
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
    ABT_V4.drop(
        ABT_V4.filter(regex="_dropMe$").columns.tolist(), axis=1, inplace=True
    )
    print("Added Unemployment data:")
    print(f"ABT.shape ={ABT_V4.shape}")

    return ABT_V4


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
        #missing 
        return -1 
    if len_fip == 4:
        return county_fips[1:]
    if len_fip == 5:
        return county_fips[2:]


if __name__ == "__main__":

    # Import data:
    intermediate_directory = os.path.abspath("data/intermediate")

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
    data_directory = os.path.abspath("data")
    file_name = "weather_by_county_fips.csv"
    weather_df = pd.read_csv(f"{data_directory}/{file_name}", error_bad_lines=False)

    # Census data 
    file_name = "ACS_full.csv"
    ACS_full_df = pd.read_csv(f"{intermediate_directory}/{file_name}")

    # Uneployment data
    file_name = "DoL_daily_county.csv"
    DoL_df = pd.read_csv(f"{data_directory}/{file_name}", error_bad_lines=False)

    # Clean uneployment: 
    DoL_df.rename(
        inplace=True,
        columns={"Date": "date", "County Name": "county", "State": "state"},
    )
    # Drop State Code -> already exists as state_code
    del DoL_df["State Code"]

    # Get ABT
    ABT_final = join_all_data()
   
    # Export Data
    check_directory = os.path.abspath("data/intermediate")
    if not os.path.exists(check_directory):
        os.makedirs(check_directory)

    # Export CDC_full_df to csv
    file_name = "ABT_V1.csv"
    ABT_final.to_csv(f"{check_directory}/{file_name}", index=False)
