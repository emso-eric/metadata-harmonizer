###  Example 15: Dataset with an unknown sensor    
Simple dataset with two CTDs, but the information of one of them has been lost and it is recorded as unknown. 
Additionally, the CSV file has an extra column not listed in the metadata, called `USELESS_COLUMN`. This columns 
should be ignored during the dataset generation with the flag `-i` or `--ignore-extra-cols`.

  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor, Unknown sensor, this information has been lost    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/15/*.yaml -d examples/15/*.csv --out example15.nc --ignore-extra-cols  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example15.nc example15 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./15)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./15.html)  
