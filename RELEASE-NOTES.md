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