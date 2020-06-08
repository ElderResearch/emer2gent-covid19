#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import timedelta
import logging
import boto3
from botocore.exceptions import ClientError


def get_labour_data() -> pd.DataFrame:
    """Source DoL data from S3 bucket
    [include link to S3 bucket]
    """

    bucket = 
    file_name = "DOL ar539 simplified (Unemployment Claims by State by week).xlsx"

    # Read in the file:
    s3 = boto3.client('s3')

    try:
        obj = s3.get_object(Bucket=bucket, Key=file_name)
    except ClientError as e:
        logging.error(e)
        return False

    # Read object into pandas df
    df = pd.read_csv(
                    obj['Body'], 
                    header=4,
                    usecols="A:H"
                    )

    return df

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


def labour_data_transformation() -> pd.DataFrame:
    """
    Take raw table as provided by the DoL then:
    Reformat the dates to be consistent
    Calculate change in unemployment and newly employed
    Extend weekly data to daily data
    Calculate daily change and interpolated figures
    :return: the final labour data table for the ABT
    """

    labour_df = get_labour_data()

    # Reformat the dates to be consistent
    labour_df['Filed week ended'] = labour_df['Filed week ended'].apply(date_parser)
    labour_df['Reflecting Week Ended'] = labour_df['Reflecting Week Ended'].apply(date_parser)

    # Calculate change in unemployment and newly employed
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

    # Calculate daily change and interpolated figures
    labour_df_ext['New_state'] = (labour_df_ext['State'] != labour_df_ext['State'].shift(1)).astype(int)
    labour_df_ext['Week_Offset'] = 6 - np.remainder(labour_df_ext.index.values,7)
    labour_df_ext['Date'] = labour_df_ext.apply(lambda x: x['Reflecting Week Ended'] - timedelta(days=x['Week_Offset']), axis=1)
    labour_df_ext['Daily_Unemployment_Change'] = labour_df_ext.groupby(['State','Reflecting Week Ended'])['Changed Unemployment']\
                                                .transform(lambda x: x // 7)
    labour_df_ext['Daily_Interp_Total_Claims'] = labour_df_ext['Total Claims'] - \
                                            labour_df_ext['Daily_Unemployment_Change']*labour_df_ext['Week_Offset']

    labour_df_ext.drop(columns=['New_state','Week_Offset'], inplace=True)

    return labour_df_ext

