#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import logging

"""
Take all of the variety of data cleaning, transformations and smoothing 
that the team members are doing and pull that into a script to document and maintain these as part of the ABT.

- Fixing the cumulative infections numbers

- Fix NAs in weather data

- Fix NAs in mobility data

- Decide a way to encode Phase 1, 2, and 3 reopening dates

- Fix NAs in the Census data

- Capture the target variable as we’ve defined it

- Capture the weighting of features

NOTE: this will be updated as we go 
"""


if __name__ == "__main__":
    
    # Check for ABT in intermediate: 
    data_dir = Path(__file__).resolve().parents[5] / "data"
    abt_path = data_dir / "intermediate" / "ABT_V1.csv"
    if not abt_path.exists(): 
        raise FileNotFoundError ("ABT_V1.csv")

    
    # Import : ABT
    ABT_raw = pd.read_csv(abt_path)
    print(ABT_raw.shape)

    # ADD : 




