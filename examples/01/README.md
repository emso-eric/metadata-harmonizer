###  Example 01: Simple dataset with only one CTD at a fixed depth    
Simple dataset with only one CTD at a fixed depth. Metadata files are split in 4 yaml files: global, platforms, sensors and variables    
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/01/*.yaml -d examples/01/*.csv --out example01.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example01.nc example01 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./01)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./01.html)  
