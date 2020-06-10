#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import timedelta
import logging

from pathlib import Path
data_dir = Path(__file__).resolve().parents[5] / "data"

def get_cdc_data() -> pd.DataFrame:
    """Source CDC infection and death data from data folder
    url = https://usafacts.org/visualizations/coronavirus-covid-19-spread-map/
    """

    infection_file_name = "covid_confirmed_usafacts.csv"
    infection_file_path = data_dir / infection_file_name
    
    death_file_name = "covid_deaths_usafacts.csv"
    death_file_path = data_dir / death_file_name

    # Read objects into pandas df
    infection_df = pd.read_csv(infection_file_path)
    death_df = pd.read_csv(death_file_path)
    
    return infection_df, death_df



def cdc_data_transformation() -> pd.DataFrame:
    """
    Take raw tables as provided by the CDC then:
    Convert tables from dates being columns to row per date entry 
    Merge the death and infection DataFrames
    :return: the final joined cdc data table for the ABT
    """

    infection_df, death_df = get_cdc_data()

    # get columns for final table and date columns to melt into single entries
    id_vars = death_df.columns.tolist()[:4]
    dates = death_df.columns.to_list()
    dates = [i for i in dates if i not in id_vars]

    # convert infection table
    infection_grouped = pd.melt(infection_df, id_vars=id_vars, value_vars=dates)
    infection_grouped.rename(columns={'variable': 'date', 'value': 'infections'}, inplace=True)

    # convert death table
    death_grouped = pd.melt(death_df, id_vars=id_vars, value_vars=dates)
    death_grouped.rename(columns={'variable': 'date', 'value': 'deaths'}, inplace=True)

    # Merge the death and infection DataFrames
    on_list = ['countyFIPS', 'stateFIPS', 'date']
    final_df = infection_grouped.merge(death_grouped, how='outer', on=on_list, suffixes=('', '_y'))
    final_df.drop(columns=['County Name_y', 'State_y'],inplace=True)
    final_df.sort_values(by=['stateFIPS','countyFIPS','date'])

    return  final_df

if __name__ == "__main__":
    df = cdc_data_transformation()
