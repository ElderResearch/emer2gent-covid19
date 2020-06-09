#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests
import math
import io
import os
import re 


def join_all_data():
    
    # -------------------------------------------------------------------------------
    # STEP 1: Join policy data to CDC data 
    # Policy data is a combination of state level & county level data 
    # For cases where we only have state level all counties are assumed to inherete state level policy data
    # O.W county specific policy data 

    # Split into disjoin data sets bassed on county & state level 
    Policy_state_df = Policy_df[Policy_df.county.isna()]
    Policy_county_df = Policy_df[~Policy_df.county.isna()]

    # Furthermore, split the CDC acoring to the fips county code 
    county_fip_with_policy = Policy_county_df.county_fip.unique()
    CDC_df_0 = CDC_df[~CDC_df.county_fip.isin(county_fip_with_policy)] # without couty level data
    CDC_df_1 = CDC_df[CDC_df.county_fip.isin(county_fip_with_policy)]  # with county level data 

    # Join compodents sepretly: [PLEASE LET ME KNOW IF THERE IS A MORE EFFICENT WAY TO DO THIS]

    # Left join to CDC_df_0 -> this will give the state policy also to the county level 
    ABT_sub_0 = pd.merge(CDC_df_0 ,Policy_state_df, 
                      how = "left" , 
                      left_on = ['state_code','date'] , 
                      right_on = ['state_code','date'],
                      suffixes=('', '_dropMe')
                     )
    
    ABT_sub_0.drop(ABT_sub_0.filter(regex='_dropMe$').columns.tolist(),axis=1, inplace=True)
    print(f"ABT_sub_0.shape ={ABT_sub_0.shape}")

    # Inner join (same size and match) on CDC_df_1 to the spicfic county polices data 
    ABT_sub_1 = pd.merge(CDC_df_1 ,Policy_county_df, 
                        how = "inner" , 
                        left_on = ['county_fip','date'] , 
                        right_on = ['county_fip','date'],
                        suffixes=('', '_dropMe')
                        )
    ABT_sub_1.drop(ABT_sub_1.filter(regex='_dropMe$').columns.tolist(),axis=1, inplace=True)
    print(f"ABT_sub_1.shape ={ABT_sub_1.shape}")

    # Concat. row-wise to get version 0 of the ABT -> [CDC,policy ]
    ABT_V0 = pd.concat([ABT_sub_0,ABT_sub_1],ignore_index = True)
    print(f"ABT_V0.shape ={ABT_V0.shape}")

    # -------------------------------------------------------------------------------
    # STEP 2: Add mobility data which is on a county level
    # We can left join to ABT_V0 on county_fip  & date
    ABT_V1 = pd.merge(ABT_V0 ,Mobility_df, 
                      how = "left" , 
                      left_on = ['county_fip','date'] , 
                      right_on = ['county_fip','date'],
                      suffixes=('', '_dropMe')
                     )
    ABT_V1.drop(ABT_V1.filter(regex='_dropMe$').columns.tolist(),axis=1, inplace=True)
    print(f"ABT_V1.shape ={ABT_V1.shape}")

    # -------------------------------------------------------------------------------
    # STEP 3: Add weather data 
    # Weather data can be joined on 
    ABT_V2 = pd.merge(ABT_V1 ,weather_df, 
                        how = "left" , 
                        left_on = ['county_fip','date'] , 
                        right_on = ['county_fip','date'],
                        suffixes=('', '_dropMe')
                        )
    ABT_V2.drop(ABT_V2.filter(regex='_dropMe$').columns.tolist(),axis=1, inplace=True)
    print(f"ABT_V2.shape ={ABT_V2.shape}")
    
    # -------------------------------------------------------------------------------
    # STEP 4: Add Census data
    # Census data is using state_fips as the prefix to the full fips AND county fips the suffix 
    # We need to create these in order to joi without dublications 
    fips_id = ABT_V2.county_fip.apply(str)
    ABT_V2["state_fip"] = fips_id.apply(parse_state).apply(int)
    ABT_V2["proxy_fip"] = fips_id.apply(parse_county).apply(int)

    # JOIN  using common keys: 
    ABT_V3 = pd.merge(ABT_V2 ,ACS_full_df, 
                      how = "left" , 
                      left_on = ["state_fip","proxy_fip"] , 
                      right_on = ["state_fips","county_fips"],
                      suffixes=('', '_dropMe')
                     )
    ABT_V3.drop(ABT_V3.filter(regex='_dropMe$').columns.tolist(),axis=1, inplace=True)
    # drop proxy: 
    del ABT_V3["proxy_fip"]
    print(f"ABT_V3.shape ={ABT_V3.shape}")

    return ABT_V3


def parse_state(county_fips):
    # Get state fips(prefix)
    len_fip = len(county_fips) 
    if len_fip == 1:
        return 1
    if len_fip == 4:
        return county_fips[0]
    if len_fip == 5:
        return county_fips[0:2]

def parse_county(county_fips):
    # get county_fips(suffix)
    len_fip = len(county_fips)
    if len_fip == 1:
        return 0 
    if len_fip == 4:
        return county_fips[1:]
    if len_fip == 5:
        return county_fips[2:]   

if  __name__ == "__main__":
    
    # Import data: 
    intermediate_directory = os.path.abspath("data/intermediate")

    # CDC Data -> from intermediate tables 
    # CDC Data will be out left table that other data will be joined to [Explain why]
    file_name = "CDC_full_data.csv"
    CDC_df = pd.read_csv(f"{intermediate_directory}/{file_name}")

    # Polic data -> intermetiate form 
    file_name = "Policy_ABT.csv"
    Policy_df = pd.read_csv(f"{intermediate_directory}/{file_name}") 

    # Mobility data for the US
    file_name = "US_mobility_data.csv"
    Mobility_df = pd.read_csv(f"{intermediate_directory}/{file_name}") 

    # Weather data 
    data_directory = os.path.abspath("data")
    file_name = "weather_by_county_fips.gz"
    weather_df = pd.read_csv(f"{data_directory}/{file_name}", compression='gzip', error_bad_lines = False)

    # Census data created by join_census_data.py
    file_name = "ACS_full.csv"
    ACS_full_df = pd.read_csv(f"{intermediate_directory}/{file_name}")

    # Get ABT 
    ABT_final = join_all_data()

    # Export Data 
    check_directory = os.path.abspath("data/processed")
    if not os.path.exists(check_directory):
        os.makedirs(check_directory)

    # Export CDC_full_df to csv 
    file_name = "ABT_V1.csv"
    ABT_final.to_csv(f"{check_directory}/{file_name}",index = False)













    
