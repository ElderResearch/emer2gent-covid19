# `Python`

Create a virtual environment using `venv` and `requirements.txt`  
1. From the root project directory: `python3 -m venv venv`
2. Activate: `source venv/bin/activate`  
3. Install requirements: `pip install -r requirements.txt`  
4. Profit! 

---
## `ABT Usage`

To replicate the ABT run the following scripts from root project directory: 
1. Run `src/python/pkg/trent/abt/transform_CDC.py` to join & transform CDC deaths and case data. This will write data to `data/intermediate/CDC_full_data.csv`. 
2. Run `src/python/pkg/trent/abt/transform_policy.py` to tranform PHE data and write to `data/intermediate/Policy_ABT.csv`.
3. Run `src/python/pkg/trent/abt/join_census_data.py` to join all ACS data and write to `data/intermediate/ACS_full.csv`.
4. Run `src/python/pkg/trent/abt/build_ABT.py` to left join all data to CDC data and write to `data/intermediate/ABT_V1.csv`.

--- 
