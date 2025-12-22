###  Example 06: ADCP in a seabed station    
Time series profile with an ADCP in a seabed station, an ADCP cell every 10 metres    
  
**sensors**: AWAC-AST 1MHz    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/06/*.yaml -d examples/06/*.csv --out example06.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example06.nc example06 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./06)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./06.html)  
