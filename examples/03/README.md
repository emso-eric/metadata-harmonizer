###  Example 03: Dataset with data from two CTDs swapped for maintenance    
Time series with data from two CTDs swapped for maintenance, only one of them is deployed at a given time. Depth is constant     
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird 16Plus V2    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/03/*.yaml -d examples/03/*.csv --out example03.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example03.nc example03 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./03)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./03.html)  
