###  Example 09: Trajectory of two AUVs equipped with CTDs    
Trajectory of two AUVs (Girona 500 and Sparus II) equipped with a SBE37 CTD    
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird 16Plus V2    
**platforms**: Girona 500 AUV SN0001, Sparus II AUV SN0001    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/09/*.yaml -d examples/09/*.csv --out example09.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example09.nc example09 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./09)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./09.html)  
