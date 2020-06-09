#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests
import math
import io
import os

pd.options.mode.chained_assignment = None 


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

We will filter for US & add the Federal Information Processing Standards (FIPS) on a county level 
- FIPS mapping can be found @ data/fips.csv from repo. root
"""



# ------- Functions ------- #

def get_google_mobility():
    """
    Download Global googles mobility data 
    Allows you to simply update the mobility data when new data is relased 
    """
    url = 'https://www.google.com/covid19/mobility/'
    print("Scraping Google Mobility data -----------")
    # Extract the link that polits to the csv 
    response_txt = requests.get(url).text #html raw  
    HTML_parse = BeautifulSoup(response_txt, "html.parser")
    tag = HTML_parse.find('a', {"class": "icon-link"})
    link = tag['href']
    
    # request link to csv & load to pandas dataFrame 
    response = requests.get(link).content
    global_df = pd.read_csv( io.StringIO(response.decode('utf-8')),low_memory = False)

    print(" -----------> Complete")
    print(f"mobility_df.shape = {global_df.shape}")
    return global_df


def filter_for_US(mobility_raw): 
    """
    Filder Globle mobility data to United States
    Further converts string date column to time stamp "Year-Month-Day"
    """
    US_mobility_df = mobility_raw[mobility_raw.country_region == 'United States']
    US_mobility_df.reset_index(inplace = True)
    US_mobility_df["date"] = US_mobility_df.date.apply(lambda x: datetime.strptime(x, "%Y-%m-%d"))

    # Drop unneeded columns: 
    # Print for time interval data exisits on & shape 
    print(f"US_mobility_df.shape = {US_mobility_df.shape}")
    t0 = US_mobility_df.sort_values("date")["date"].iloc[0]
    tn = US_mobility_df.sort_values("date")["date"].iloc[-1]
    print(f"Time-Period: {t0} to {tn}")

    return US_mobility_df


def add_fips(US_mobility_df,fips_df): 
    """
    Join fips data to mobility data usinfg state & county columns (left join)
    returns data with added [county_fip, state_code]
    """
    JOIN_df  = pd.merge(US_mobility_df ,fips_df, 
                      how = 'left' , 
                      left_on = ['state','county'] , 
                      right_on = ['state','county']
                     )
    print(f"JOIN_df.shape = {JOIN_df.shape}")
    return JOIN_df


if  __name__ == "__main__":
    
    # Import global google mobility data & filter for US ;
    print(os.getcwd()) 
    mobility_raw = get_google_mobility()
    US_mobility_df = filter_for_US(mobility_raw)

    # Columns renamed for consistency across tables unique idetifying keys 
    # Drop percent_change_from_baseline suffix for more compact representation 
    US_mobility_df.rename(
                inplace = True , 
                columns = {
                            'sub_region_1': 'state', 
                            'sub_region_2': 'county', 
                            'country_region_code': 'country', 
                            'retail_and_recreation_percent_change_from_baseline': 'retail_and_recreation_percent',
                            'grocery_and_pharmacy_percent_change_from_baseline': 'grocery_and_pharmacy',
                            'parks_percent_change_from_baseline' : "parks",
                            'transit_stations_percent_change_from_baseline' : 'transit_stations',
                            'workplaces_percent_change_from_baseline': 'workplaces',
                            'residential_percent_change_from_baseline' : 'residential'
                        }
                ) 

    # Disctrict of Columbia can be assumed as a county -> replace missing county enrty with 'state' name 
    US_mobility_df.loc[US_mobility_df.state == "District of Columbia","county"] = "District of Columbia"

    # Import and join fips.csv to US_mobility -> this is one of our unique idetifying keys 
    # fips.csv exisits in data folder create by python src/python/init_project.py
    fips_abs_path = os.path.abspath("data/fips.csv")
    print(fips_abs_path)
    fips_df = pd.read_csv(fips_abs_path)
    US_mobility_df = add_fips(US_mobility_df,fips_df)

    # Filter: Drop the missing values in state & county - we cant idetify their fips code on all levels 
    US_mobility_df = US_mobility_df[~US_mobility_df.state.isna()]
    US_mobility_df = US_mobility_df[~US_mobility_df.county.isna()]

    # Drop Columns that are redundent 
    del US_mobility_df["index"]
    del US_mobility_df["country"]
    del US_mobility_df["country_region"]
    
    # Export: Check that intermediate data folder exisits O.W create 
    check_directory = os.path.abspath("data/intermediate")
    print(check_directory)
    if not os.path.exists(check_directory):
        os.makedirs(check_directory)

    # Export US_mobility_df to csv 
    file_name = "US_mobility_data.csv"
    US_mobility_df.to_csv(f"{check_directory}/{file_name}",index = False)



