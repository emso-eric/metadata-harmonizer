###  Example 15: Dataset with an unknown sensor    
Simple dataset with two CTDs, but the information of one of them has been lost and it is recorded as unknown    
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor, Unknown sensor, this information has been lost    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/15/*.yaml -d examples/15/*.csv --out example15.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example15.nc example15 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./15)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./15.html)  
