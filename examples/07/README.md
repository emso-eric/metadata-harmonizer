###  Example 07: Two ADCPs, one mounted in a seabed station and another in a buoy    
Two ADCPs, one mounted in a seabed station and another in a buoy    
  
**sensors**: AWAC-AST 1MHz 0001, AWAC-AST 1MHz 0002    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/07/*.yaml -d examples/07/*.csv --out example07.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example07.nc example07 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./07)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./07.html)  
