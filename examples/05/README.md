###  Example 05: 3 deployments of the same mooring, equipped with 4 CTDs and a surface weather station    
Dataset with 3 deployments of the same mooring, equipped with 4 CTDs and a surface weather station. The lat/lon coordinates are a bit different in every deployment and the sensors may change positions    
  
**sensors**: Airmar 200WX weather station, Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird Scientific SBE37 SMP CTD Sensor    
**platforms**: ODASItalia1    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/05/*.yaml -d examples/05/*.csv --out example05.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example05.nc example05 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./05)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./05.html)  
