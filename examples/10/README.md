###  Example 10: ASV equipped with an ADCP    
Trajectory data from an ASV with current profiles from an ADCP    
  
**sensors**: AWAC-AST 1MHz    
**platforms**: OBSEA Seafloor Observatory    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/10/*.yaml -d examples/10/*.csv --out example10.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example10.nc example10 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./10)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./10.html)  
