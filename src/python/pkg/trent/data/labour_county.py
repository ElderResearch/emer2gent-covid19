#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import timedelta
import logging

from pathlib import Path
data_dir = Path(__file__).resolve().parents[5] / "data"

def get_DoL_data() -> pd.DataFrame:
    """Source DoL weekly state unemployment data from data folder
    url = https://oui.doleta.gov/unemploy/claims.asp
    """

    file_name = "DOL ar539 simplified (Unemployment Claims by State by week).xls"

    file_path = data_dir / file_name

    # Read object into pandas df
    df = pd.read_excel(
                    file_path, 
                    header=4,
                    usecols="A:H"
                    )

    return df

def get_DoL_county_data() -> pd.DataFrame:
    """Source BLS monthly unemployment county level data from data folder
    url = https://www.bls.gov/lau/#cntyaa
    """

    file_name = "laucntycur14.xlsx"

    file_path = data_dir / file_name

    # Read object into pandas df
    df = pd.read_excel(
                    file_path, 
                    header=None,
                    skiprows=6,
                    usecols="A:J",
                    parse_dates=[4]
                    )

    return df

def get_fips_data():
    """Source fips data from data folder
    url = https://en.wikipedia.org/wiki/List_of_United_States_FIPS_codes_by_county, https://en.wikipedia.org/wiki/Federal_Information_Processing_Standard_state_code
    create state and state_fip code map for later use
    """

    file_name = "fips.csv"

    file_path = data_dir / file_name

    # Read object into pandas df
    fips_df = pd.read_csv(
                    file_path
                    )

    state_map={k: list(v)[0] for k, v in fips_df.groupby('state')['state_code']}
    state_fip_map={k: list(v)[0] for k, v in fips_df.groupby('state_fip')['state_code']}


    return state_map, state_fip_map

def date_parser(x):
    """
    Converts current mismatched (2 forms) date to single consistent date format
    :param: current date format
    :return: new consistent date format
    """

    x_str = str(x)

    if x_str[:4] == '2020': 
        day = x_str[5:7]
        month = x_str[8:10]
        year = x_str[:4]
        x_form = pd.to_datetime(f'{int(year)}-{int(month)}-{int(day)}') 
        
    else: x_form = pd.to_datetime(x, dayfirst=False, yearfirst=False)
        
    return x_form


def labour_state_transformation() -> pd.DataFrame:
    """
    Take raw table as provided by the DoL for weekly state level unemployment then:
    Reformat the dates to be consistent
    Calculate change in unemployment and newly employed
    Extend weekly data to daily data
    Calculate daily change and interpolated figures
    Prepare columns for later merge
    :return: the final state labour data table for merging with county level
    """

    labour_df = get_DoL_data()

    # Reformat the dates to be consistent
    labour_df['Filed week ended'] = labour_df['Filed week ended'].apply(date_parser)
    labour_df['Reflecting Week Ended'] = labour_df['Reflecting Week Ended'].apply(date_parser)

    # Calculate change in unemployment and newly employed
    labour_df['Total Claims'] = labour_df['Initial Claims'] + labour_df['Continued Claims']
    labour_df['Last Week Unemployed'] = labour_df['Total Claims'].shift(1)
    labour_df['New_state'] = (labour_df['State'] != labour_df['State'].shift(1)).astype(int)
    labour_df['Last Week Unemployed'] = labour_df.apply(lambda x: x['Total Claims'] if x['New_state'] == 1
                                                        else x['Last Week Unemployed'], axis=1
                                                    )
    labour_df['Changed Unemployment'] = labour_df['Total Claims'] - labour_df['Last Week Unemployed']

    labour_df['Newly Employed'] = labour_df['Last Week Unemployed'] - labour_df['Continued Claims']
    labour_df['Newly Employed'] = labour_df['Newly Employed'].apply(lambda x: max(0, x))

    labour_df.drop(columns=['Last Week Unemployed', 'New_state'], inplace=True)


    # Extend weekly data to daily data
    labour_df_ext = pd.DataFrame(np.repeat(labour_df.values,7,axis=0))
    labour_df_ext.columns = labour_df.columns
    labour_df_ext.sort_values(by=['State','Filed week ended'], inplace=True)

    # format columns correctly
    labour_df_ext[['Initial Claims', 'Continued Claims', 'Total Claims', 'Covered Employment', 'Changed Unemployment', 'Newly Employed']]\
        =labour_df_ext[['Initial Claims', 'Continued Claims', 'Total Claims', 'Covered Employment', 'Changed Unemployment', 'Newly Employed']].astype(int)
    labour_df_ext['Insured Unemployment Rate'] = labour_df_ext['Insured Unemployment Rate'].astype(float)

    # Calculate daily change and interpolated figures
    labour_df_ext['New_state'] = (labour_df_ext['State'] != labour_df_ext['State'].shift(1)).astype(int)
    labour_df_ext['Week_Offset'] = 6 - np.remainder(labour_df_ext.index.values,7)
    labour_df_ext['Date'] = labour_df_ext.apply(lambda x: x['Reflecting Week Ended'] - timedelta(days=x['Week_Offset']), axis=1)

    labour_df_ext.drop(columns=['New_state'], inplace=True)

    # map State to state_code for merge
    state_map, state_fip_map = get_fips_data()
    labour_df_ext['state_code'] = labour_df_ext['State'].map(state_map)

    return labour_df_ext

def labour_county_transformation() -> pd.DataFrame:
    """
    Take raw table as provided by BLS for monthly county level unemployment then:
    Rename columns for clarity
    Reformat date column and filter before start of 2020 year
    Clean up the state information for merging
    Rescale unemployment rate
    Extend April data to May because the latter not yet available
    Calculate county level contribution to state level unemployment
    :return: the final county labour data table for merging with state level
    """

    col_names = {
        0: "LAUS Code",
        1: "State FIPS Code",
        2: "County FIPS Code",
        3: "County Name/State Abbreviation",
        4: "Period",
        5: "Labor Force",
        6: "Employed",
        7: "Unemployed",
        8: "Unemployment Rate (%)"
    }
    
    county_labour = get_DoL_county_data()

    state_map, state_fip_map = get_fips_data()

    # Rename columns for clarity
    county_labour.rename(columns=col_names, inplace=True)

    # Filter out non essential states
    county_labour = county_labour.loc[county_labour['State FIPS Code']<=56]

    # Adjust for April 2020 results currently being preliminary, format and filter out pre 2020
    county_labour['Period'] = county_labour['Period'].apply(lambda x: str(x)[:6])
    county_labour['Period'] = pd.to_datetime(county_labour['Period'],format="%b-%y")
    county_labour = county_labour.loc[county_labour['Period']>="2020-01-01"]

    # clean up the state information for merging
    county_labour['State FIPS Code'] = county_labour['State FIPS Code'].astype(int)
    county_labour['County FIPS Code'] = county_labour['County FIPS Code'].astype(int)
    county_labour['County Name'] = county_labour['County Name/State Abbreviation'].str.split(pat=",",expand=True).iloc[:,0]
    county_labour['State Code'] = county_labour['State FIPS Code'].map(state_fip_map)
    county_labour['county_fip'] = county_labour['State FIPS Code'].astype(str) + county_labour['County FIPS Code'].astype(str).str.zfill(3)

    county_labour.drop(columns=['LAUS Code',
                            'County Name/State Abbreviation', 
                            'State FIPS Code',
                            'County FIPS Code'
                           ], 
                        inplace=True)


    # Rescale unemployment rate
    county_labour['Unemployment Rate (%)'] = county_labour['Unemployment Rate (%)'] / 100

    # Extend April data to May because the latter not yet available
    county_labour_may = county_labour.loc[county_labour['Period'].dt.month==4].copy()
    county_labour_may['Period'] = pd.to_datetime("2020-05-01")
    county_labour = county_labour.append(county_labour_may,ignore_index=True)
    county_labour.reset_index(drop=True,inplace=True)

    # Calculate county level contribution to state level unemployment
    county_labour['County Contrib to State Unemployment'] = county_labour.groupby(['State Code','Period'])['Unemployed'].apply(lambda x:
                                                                           x/x.sum()
                                                                           )

    # format number columns
    county_labour[['Labor Force','Employed','Unemployed','county_fip']] = county_labour[['Labor Force','Employed','Unemployed','county_fip']].astype(int)
    county_labour[['Unemployment Rate (%)','County Contrib to State Unemployment']] = county_labour[['Unemployment Rate (%)','County Contrib to State Unemployment']].astype(float)

    return county_labour

def merge_state_county() -> pd.DataFrame:
    """
    Take formatted state and county level unemployment data:
    Merge two unemployment tables them on state_code and remove non-essential entries created by merge
    Calculate County level data from State level data
    Create the County daily values for the ABT
    Choose key columns for merging into the ABT
    :return: the final county labour data table for merging with state level
    """
    

    labour_df_ext = labour_state_transformation()
    county_labour = labour_county_transformation()

    # Merge two unemployment tables them on state_code
    labour_combined = labour_df_ext.merge(county_labour, how='outer', left_on='state_code', right_on='State Code')

    # Remove non-essential entries created by merge
    labour_combined = labour_combined[~labour_combined['state_code'].isna()]
    labour_combined = labour_combined[(labour_combined['Date'].dt.month==labour_combined['Period'].dt.month)]

    # Calculate County level data from State level data
    labour_combined['County Initial Claims'] = labour_combined['Initial Claims']*labour_combined['County Contrib to State Unemployment']
    labour_combined['County Continued Claims'] = labour_combined['Continued Claims']*labour_combined['County Contrib to State Unemployment']
    labour_combined['County Total Claims'] = labour_combined['Total Claims']*labour_combined['County Contrib to State Unemployment']
    labour_combined['County Changed Unemployment'] = labour_combined['Changed Unemployment']*labour_combined['County Contrib to State Unemployment']

    # Create the County daily values for the ABT
    labour_combined['County_Daily_Unemployment_Change'] = labour_combined.groupby(['State','Reflecting Week Ended'])['County Changed Unemployment']\
                                            .transform(lambda x: x / 7)
    labour_combined['County_Daily_Interp_Total_Claims'] = labour_combined['County Total Claims'] - \
                                        labour_combined['County_Daily_Unemployment_Change']*labour_combined['Week_Offset']

    # format the value columns
    labour_combined = labour_combined.round({'County Initial Claims':0, 
                                         'County Continued Claims':0, 
                                         'County Total Claims':0,
                                         'County Changed Unemployment':0,
                                         'County_Daily_Unemployment_Change':0,
                                         'County_Daily_Interp_Total_Claims':0
                                        })

    # Choose key columns for merging into the ABT
    labour_final = labour_combined[[
                        'State',
                        'State Code',
                        'County Name',
                        'county_fip',
                        'Date',
                        'Labor Force',
                        'Unemployed',
                        'County_Daily_Unemployment_Change',
                        'County_Daily_Interp_Total_Claims'
                    ]]

    return labour_final

if __name__ == "__main__":
    df = merge_state_county()