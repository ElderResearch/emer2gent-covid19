echo 'running transform_CDC.py --------------'
python src/python/pkg/trent/abt/transform_CDC.py
echo 'running transform_policy.py ---------------'
python src/python/pkg/trent/abt/transform_policy.py
echo 'running join_census_data.py ---------------'
python src/python/pkg/trent/abt/join_census_data.py 
echo 'running join_census_data.py ---------------'
python src/python/pkg/trent/abt/build_ABT.py 




