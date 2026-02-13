###  Example 02: Two CTDs deployed at different depths    
Simple dataset with two CTDs at fixed depths. Metadata is inside a single yaml file    
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird 16Plus V2    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/02/*.yaml -d examples/02/*.csv --out example02.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example02.nc example02 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./02)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./02.html)  
