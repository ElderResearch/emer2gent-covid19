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
Overview:
Join all the ASC data into one table 
dump into intermediate data folder 
this helps neaten up the construction of the ABT 
"""


#------- Functions --------# 
def join_asc_pair(DF_1,DF_2):
    # Join two ASC data frame by state_fips and county_fips (inner) as the match perfectly 
    
    JOIN_df = pd.merge(DF_1 ,DF_2,
                      how = "inner" , 
                      left_on = ["state_fips","county_fips"] , 
                      right_on = ["state_fips","county_fips"],
                      suffixes=('', '_dropMe')
              )
    
    print(f"JOIN_df.shape ={JOIN_df.shape}")
    return JOIN_df


if  __name__ == "__main__":
    
    data_directory = os.path.abspath("data")
    
    # Polulation Data 
    file_name = "acs_dem_pop.csv.gz"
    ACS_pop_df = pd.read_csv(f"{data_directory}/{file_name}", compression='gzip', error_bad_lines=False)
    print(f"ASC_pop_df .shape ={ACS_pop_df.shape}")

    # Race Data 
    file_name = "acs_dem_race.csv.gz"
    ACS_race_df = pd.read_csv(f"{data_directory}/{file_name}", compression='gzip', error_bad_lines=False)
    print(f"ASC_race_df .shape ={ACS_pop_df.shape}")

    # Income Data 
    file_name = "acs_dem_median_hh_income.csv.gz"
    ACS_income_df = pd.read_csv(f"{data_directory}/{file_name}", compression='gzip', error_bad_lines=False)
    print(f"ASC_income_df .shape ={ACS_pop_df.shape}")

    # Age, Demog. Gender 
    file_name = "acs_dem_age_gender.csv.gz"
    ACS_DAG_df = pd.read_csv(f"{data_directory}/{file_name}", compression='gzip', error_bad_lines=False)
    print(f"ASC_DAG_df .shape ={ACS_DAG_df.shape}")

    # Join data in a sequetial manner:
    ACS_0 = join_asc_pair(DF_1=ACS_pop_df,DF_2=ACS_race_df) # POP & RACE 
    ACS_1 = join_asc_pair(DF_1=ACS_0,DF_2=ACS_income_df)
    ACS_2 = join_asc_pair(DF_1=ACS_1,DF_2=ACS_DAG_df)


     # Export Data 
    check_directory = os.path.abspath("data/intermediate")
    if not os.path.exists(check_directory):
        os.makedirs(check_directory)

    # Export CDC_full_df to csv 
    file_name = "ACS_full.csv"
    ACS_2.to_csv(f"{check_directory}/{file_name}",index = False)



    