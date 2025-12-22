###  Example 13: Generate and convert Copernicus-like NetCDF files to EMSO-compliant ERDDAP Dataset    
Simple Copernicus-like dataset that will be converted on-the-fly to EMSO-compliant dataset using NcML and some tricks in datasets.xml    
  
**sensors**: Sea-Bird Scientific SBE16    
**platforms**: OBSEA Seafloor Observatory    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/13/*.yaml -d examples/13/*.csv --out example13.nc  --keep 
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example13.nc example13 /path/to/nc/files -m examples/./13/mapping.yaml 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./13)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./13.html)  
* 🔀 This example uses a `mapping.yaml` file to adjust the source / destination names and to override metadata attributes  
* ⚙️ This example uses [NcML](https://docs.unidata.ucar.edu/netcdf-java/current/userguide/ncml_overview.html) to create a virtual dataset in order to add/modify variables on-the-fly without modifying the underlying NetCDF files.  
* 🔏 This example uses the `--keep` flag to maintain the original upper case coordinate names following Copernicus style  
