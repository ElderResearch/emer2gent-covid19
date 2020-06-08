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


# UPDATE: There is a pandas implmentation to exactly this (melt)
"""



# ------- Helper Functions ------- #

def reformat_cdc_date(cdc_date_form):
    """
    Date in raw CDC takes the form month/day/year
    To be consistent in date across tables map to year-month-day 
    """
    cdc_date_form += '20' # 20 -> 2020 (this works are we only collect for 2020)
    split = cdc_date_form.split("/") #[month,day,year]
    month = split[0]
    day = split[1]
    year = split[2]
    
    # Reformat to desired format
    new_date = f"{year}-{month}-{day}"
    return new_date

def row_to_df(row_index,CDC_df,obs_name = "deaths"):
    """
    Converst a row of the CDC data into desired cross sectional data 
    obs_name will give name of the observations column eg. death or confirmed 
    """    

    # Extract date columns 
    date_columns = [k for k in CDC_df.columns if bool(re.search(r'\d', k))]
    row_data = CDC_df.iloc[row_index,:]
    # Get time indpendent columns 
    row_fips_code = row_data.loc["county_fip"]
    row_county = row_data.loc["county"]
    row_state_code = row_data.loc["state_code"]
    # Get observatins eg. deaths or confirmed as a list 
    _obs = row_data.loc[date_columns].tolist() 
    
    # Build df: 
    row_df = pd.DataFrame({obs_name:_obs}) # add obs. data 
    row_df["date"] = [reformat_cdc_date(k) for k in date_columns] # add date -> reformat 
    row_df["date"] = row_df.date.apply(lambda x: datetime.strptime(x, "%Y-%m-%d")) # convert to time stamp 
    row_df["county"] = row_county # add county 
    row_df["county_fip"] = row_fips_code # add county fips
    row_df["state_code"] = row_state_code # add state code 
    
    return row_df   

def to_cross_sectional_df(CDC_df,obs_name): 
    """
    Converst full CDC_df to cross sectonal form
    obs_name controll if it deaths or confirmed we are looking at 
    """    

    # List of dataframes -> to be filled 
    list_of_df = []  
    n_rows = len(CDC_df) 
    # Run row_to_df over all CDC rows ie. get for all counties 
    for i in range(n_rows):

        sub_df = row_to_df(row_index = i ,
                           CDC_df = CDC_df,
                           obs_name = obs_name
                          )
        list_of_df.append(sub_df)
    # Join by row into one large data frame 
    CS_df = pd.concat(list_of_df,ignore_index = True)
    print(f"CS_df.shape = {CS_df.shape}")
    return CS_df


if  __name__ == "__main__":
    
    # Import data
    path_deaths = os.path.abspath("data/covid_deaths_usafacts.csv")
    path_confirmed = os.path.abspath("data/covid_confirmed_usafacts.csv") 
    CDC_deaths = pd.read_csv(path_deaths) ; print(f"CDC_deaths.shape = {CDC_deaths.shape}")
    CDC_confirmed = pd.read_csv(path_confirmed) ; print(f"CDC_confirmed.shape = {CDC_confirmed.shape}")


    # Columns renamed for consistency across tables unique idetifying keys 
    CDC_deaths.rename(
                    inplace = True , 
                    columns = {
                                "countyFIPS":"county_fip",
                                "County Name": "county",
                                "State": "state_code"
                            }
                    ) 

    CDC_confirmed.rename(
                    inplace = True , 
                    columns = {
                                "countyFIPS":"county_fip",
                                "County Name": "county",
                                "State": "state_code"
                            }
                    ) 

    CDC_deaths_df = to_cross_sectional_df(CDC_df = CDC_deaths,obs_name="deaths")
    CDC_confirmed_df = to_cross_sectional_df(CDC_df = CDC_confirmed,obs_name="confirmed")

    # By construction both tables match up perfectly
    # Add confirmed colums to fina data frame 
    CDC_full_df = CDC_deaths_df.copy()
    if all(CDC_confirmed_df.date == CDC_deaths_df.date) & all(CDC_confirmed_df.county_fip == CDC_deaths_df.county_fip):
        print("Adding confirmed cases -------------------")
        CDC_full_df["confirmed"] = CDC_confirmed_df["confirmed"]
    else:
         print("Data not matched")

    # Reorder columns: 
    new_column_order = ["date","county_fip","state_code","county","deaths","confirmed"]
    CDC_full_df = CDC_full_df.loc[:,new_column_order]


    # Export: Check that intermediate data folder exisits O.W create 
    check_directory = os.path.abspath("data/intermediate")
    print(check_directory)
    if not os.path.exists(check_directory):
        os.makedirs(check_directory)

    # Export CDC_full_df to csv 
    file_name = "CDC_full_data.csv"
    CDC_full_df.to_csv(f"{check_directory}/{file_name}",index = False)