
# EMSO ERIC Dataset Examples 
 
Here you can find an extensive list of examples on how to generate NetCDF datasets and how to integrate them into an 
ERDDAP server. All the examples in this folder are deployed in the [NetCDF-dev ERDDAP](https://netcdf-dev.obsea.es/erddap/index.html). The configuration of this 
ERDDAP can be found in the [example datasets](https://github.com/emso-eric/example-datasets) repository, including the [datasets.xml](https://github.com/emso-eric/example-datasets/blob/main/conf/datasets.xml) file. 

The commands listed here assume that the user is using a Linux shell or [WSL](https://ubuntu.com/desktop/wsl) and the current directory is the root folder of the metadata harmonizer.


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


###  Example 02: Two CTDs deployed at different depths    
Simple dataset with two CTDs at fixed depths. Metadata is inside a single yaml file    
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird 16Plus V2    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/02/*.yaml -d examples/02/*.csv --out example02.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example02.nc example02 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./02)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./02.html)  


###  Example 03: Dataset with data from two CTDs swapped for maintenance    
Time series with data from two CTDs swapped for maintenance, only one of them is deployed at a given time. Depth is constant     
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor, Sea-Bird 16Plus V2    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/03/*.yaml -d examples/03/*.csv --out example03.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example03.nc example03 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./03)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./03.html)  


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


###  Example 08: AUV trajectory with a CTD    
AUV acquiring CTD data over a trajectory    
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor    
**platforms**: Girona 500 AUV SN0001    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/08/*.yaml -d examples/08/*.csv --out example08.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example08.nc example08 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./08)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./08.html)  


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


###  Example 11: Fish detections from underwater pictures, compatible with Darwin Core    
Fish detections from an underwater pictures analyzed through an object detection and classification algorithm trained to classify fish    
  
**sensors**: IPC608 underwater camera    
**platforms**: OBSEA Seafloor Observatory    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/11/*.yaml -d examples/11/*.csv --out example11.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example11.nc example11 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./11)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./11.html)  


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


###  Example 15: Dataset with an unknown sensor    
Simple dataset with two CTDs, but the information of one of them has been lost and it is recorded as unknown    
  
**sensors**: Sea-Bird Scientific SBE37 SMP CTD Sensor, Unknown sensor, this information has been lost    
**platforms**: OBSEA seabed station    
  
NetCDF generation command:  
```bash
python3 generator.py -m examples/15/*.yaml -d examples/15/*.csv --out example15.nc  
```
  
ERDDAP configuration:  
```bash
python3 erddap_config.py example15.nc example15 /path/to/nc/files 
```
  
  
**Additional info**:  
* 📂 [Explore the source files](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/./15)  
* 🔗 [ERDDAP dataset](https://netcdf-dev.obsea.es/erddap/tabledap/./15.html)  

