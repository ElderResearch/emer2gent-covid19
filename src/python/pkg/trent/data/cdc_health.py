#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import timedelta
import logging
import boto3
from botocore.exceptions import ClientError


def get_cdc_data() -> pd.DataFrame:
    """Source CDC infection and death data from S3 bucket
    [include link to S3 bucket]
    """

    bucket = 
    infection_file_name = "covid_confirmed_usafacts.csv"
    death_file_name = "covid_deaths_usafacts.csv"


    # Read in the file:
    s3 = boto3.client('s3')

    try:
        obj_infection = s3.get_object(Bucket=bucket, Key=infection_file_name)
        obj_death = s3.get_object(Bucket=bucket, Key=death_file_name)
    except ClientError as e:
        logging.error(e)
        return False

    # Read objects into pandas df
    infection_df = pd.read_csv(obj_infection['Body'])
    death_df = pd.read_csv(obj_death['Body'])
    
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
