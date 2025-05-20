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
