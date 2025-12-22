###  Example 12: Acoustic recordings from a Hydrophone    
Example of a list of recordings from a hydrophone at OBSEA    
  
**sensors**: Bjørge-NAXYS Ethernet 02345 Hydrophone    
**platforms**: OBSEA Seafloor Observatory    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/12/*.yaml -d examples/12/*.csv --out example12.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example12.nc example12 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./12)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./12.html)  
