## version 1.0 ##
1. Major modifications in all the project to adapt to the new metadata specifications
2. Using unique metadata YAML files instead of the old .min.json / .full.json files
3. Major changes in WaterFrame class
4. Adding operational tests to ensure data usage
5. Adding oso viewer
6. Adding 15 examples
7. Ensuring compatibility with Climate and Forecast

## version 0.4.7 ##
1. Adding multisensor metadata option to keep the sensor metadata sensors even if one of them has no data. 

## version 0.4.7 ##
1. Fixing errors that silently dropped rows when generating NetCDF files

## version 0.4.6 ##
1. Updating JSON-ld parser to match changes in SeaDataNet vocabs

## version 0.4.5 ##
1. Fixing threadify arguments
2. Fixing erddap_config arguments
3. Fixing 2CTDs examples README

## version 0.4.4 ##
1. Fixing inconsistencies with PyPi

## version 0.4.3 ##
1. Improved API to generate datasets, now can be called with dicts and DataFrames (before only with files)
2. Removing mooda dependencies (this time for sure)
3. Adding option to reuse EmsoMetadata, speeding up creation of multiple datasets
4. Removing most prints to clear stout

## version 0.4.2 ##

**changes**:
1. Converter generator/reporter/erddap_config into callable functions (before it was only cli)
2. Packed and published project in pypi
3. Adding testing with unittests
4. Removed mooda and reimplemented a lightweight version of WaterFrame