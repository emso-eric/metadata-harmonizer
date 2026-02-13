###  Example 14: Setup a EMSO-compliant dataset from Copernicus-like files    
Setup a EMSO-compliant dataset from Copernicus-like files. Source files from W1M3A have been slightly modified to convert the sensor_id to a string (instead of a numerical variable) and some variables have been removed    
  
**sensors**: Vaisala HMP155 hygrometer series, Sea-Bird SBE 37 MicroCat CTP (submersible) CTD sensor series, Sea-Bird SBE 16Plus V2 SEACAT C-T Recorder, Sea-Bird SBE 37 MicroCat CTP (submersible) CTD sensor series, Sea-Bird SBE 37 MicroCat CTP (submersible) CTD sensor series    
**platforms**: ODASItalia1    
  
ERDDAP configuration:  
```bash
python3 erddap_config.py examples/./14/OS_W1M3A_20250731_R_SIMPLIFIED.nc example14 /path/to/nc/files -m examples/./14/mapping.yaml 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./14)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./14.html)  
* 🔀 This example uses a `mapping.yaml` file to adjust the source / destination names and to override metadata attributes  
* ⚙️ This example uses [NcML](https://docs.unidata.ucar.edu/netcdf-java/current/userguide/ncml_overview.html) to create a virtual dataset in order to add/modify variables on-the-fly without modifying the underlying NetCDF files.  
* 📦 This example relies on existing NetCDF files! no need to generate new ones    
