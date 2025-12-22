###  Example 04: Mooring with 4 CTDs and a surface weather station    
Mooring with 4 CTDs and a surface weather station, CTDs at 100, 200, 300 and 400m depth.    
  
**sensors**: Airmar 200WX weather station, Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird Scientific SBE37 SMP CTD Sensor    
**platforms**: ODASItalia1    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/04/*.yaml -d examples/04/*.csv --out example04.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example04.nc example04 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./04)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./04.html)  
