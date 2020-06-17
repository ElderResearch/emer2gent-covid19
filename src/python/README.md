# `Python`

Create a virtual environment using `venv` and `requirements.txt`  
1. From the root project directory: `python3 -m venv venv`
2. Activate: `source venv/bin/activate`  
3. Install requirements: `pip install -r requirements.txt`  
4. Profit! 

--- 

# `Analytical Base Table (ABT)`

## `Description`

The ABT aggregates the following data sets into one data set: 
1. Center for Disease and Preventions (CDC) confirmed cases & deaths data (https://www.cdc.gov/coronavirus/2019-ncov/cases-updates/index.html)
2. US Google Mobility data (https://www.google.com/covid19/mobility/)
3. National Weather Services, Automated Surface Observing System (ASOS) data (https://www.weather.gov/asos/asostech )
4. Department of Labour Unemployment Claims (https://oui.doleta.gov/unemploy/claims.asp)
5. American Community Survey (ACS) data (https://www.census.gov/programs-surveys/acs/data.html) 
6. COVID tracking data (https://covidtracking.com/) 
7. US Land Area Data (https://www.census.gov/library/publications/2011/compendia/usa-counties-2011.html) 
8. Public Health England US Summary Statistics

All data excluding COVID tracking and PHE are collected at a county level. Note there are cases in the PHE data that are at a county level but otherwise it is state-level data. 

## `Usage`

To replicate the ABT run the following scripts from root project directory: 
1. Run `transform_CDC.py` to join & transform CDC deaths and case data. This will write data to `data/intermediate/CDC_full_data.csv`. 
2. Run `transform_policy.py` to tranform PHE data and write to `data/intermediate/Policy_ABT.csv`.
3. Run `join_census_data.py` to join all ACS data and write to `data/intermediate/ACS_full.csv`.
4. Run `build_ABT.py` to left join all data to CDC data and write to `data/processed/ABT_V1.csv`.
