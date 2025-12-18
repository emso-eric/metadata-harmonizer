# Dataset Examples #

This folder contains examples on how to generate datasets following EMSO Metadata Specifications

## Example 1: a single CTD ##
This example is a dataset containing data from a single CTD deployed at a fixed location  
**sensors**: SBE37 (CTD)  
**CF featureType**: `timeSeries`

## Example 2: two CTDs ##
A dataset combining data from two CTDs at different depths  
**sensors**: SBE16 at 10m and SBE37 at 20m  
**CF featureType**: `timeSeries`



python3 generator.py  --data examples/example01/SBE37.csv --metadata examples/example01/SBE37.min.json --output example01.nc
  
python3 generator.py  --data examples/example02/SBE16.csv examples/example02/SBE37.csv --metadata examples/example02/SBE16.min.json examples/example02/SBE37.min.json --output example02.nc
  
python3 generator.py  --data examples/example03/SBE16.csv examples/example03/SBE37.csv --metadata examples/example03/SBE16.min.json examples/example03/SBE37.min.json --output example03.nc  

python3 generator.py  --data examples/example04/AimarWeatherStation.csv examples/example04/SBE37_100m.csv examples/example04/SBE37_200m.csv examples/example04/SBE37_300m.csv  examples/example04/SBE37_400m.csv --metadata examples/example04/Airmar200WX.min.json examples/example04/SBE37-100.min.json examples/example04/SBE37-200.min.json  examples/example04/SBE37-300.min.json examples/example04/SBE37-400.min.json --output examples/example04/example04.nc

python3 generator.py  --data examples/example05/AWAC.csv --metadata examples/example05/AWAC.min.json --output examples/example05/example05.nc

python3 generator.py  --data examples/example06/AWAC_AST_1.csv examples/example06/AWAC_AST_2.csv --metadata examples/example06/AWAC1.min.json examples/example06/AWAC2.min.json  --output examples/example06/example06.nc
