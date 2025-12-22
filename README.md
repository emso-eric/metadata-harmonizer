# Metadata Harmonizer Toolbox #
This repository contains a set of tools that can be used to create NetCDF files, integrate them into an ERDDAP server 
and to ensure the compliance with the [EMSO Metadata Specifications](https://github.com/emso-eric/emso-metadata-specifications/tree/develop).

The main tools contained in this repository are:
* `generator.py`: creates EMSO-compliant NetCDF files from `.csv` and `.yaml` files  
* `erddap_config.py`: integrates NetCDF files into an ERDDAP server
* `metadata_report.py`: check the compliance of a dataset with the specifiations.

This project comes with a comprehensive example list  



## 🚀 Project Setup ##
### Prerequisites
Previous requirements are `python` 3.8+,`git` and `pip`. All commands here are for unix-like OS, for windows users it is strongly recommended to use [Ubuntu WSL](https://ubuntu.com/desktop/wsl). 

### Installation
To use this repository, just clone and install its requirements: 
1. Clone this repository
```bash
git clone https://github.com/emso-eric/metadata-harmonizer
```
2. Enter the folder:
```bash
cd metadata-harmonizer
```
3. Install the requirements:
```bash
git clone https://github.com/emso-eric/metadata-harmonizer
cd metadata-harmonizer
pip3 install -r requirements.txt
```


## 🛠 NetCDF Generator ##

The NetCDF generator creates EMSO-compliant NetCDF datasets from one or more CSV files. The basic workflow is as follows:
1. Encode your **data** as csv files, preferably one file per sensor. Add a `sensor_id` with the identifier of your sensor. Remember to add your QC columns as well 
2. Write the metadata for your dataset in one or more yaml files. It should include the following sections `global`, `variables`, `platforms` and `sensors`.
3. Run the `generator.py` script:

```bash 
python3 generator.py -d <csv files> -m <yaml files> --out <NetCDF file>
```

In the [examples folder](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples) there is a comprehensive list of examples that you can check. For instance, to generate the nc file for the first example:

```bash
python3 generator.py -m examples/01/*.yaml -d examples/01/*.csv --out example01.nc  
```

### Options:
* `-d` or `--data`: List of csv files containing the data (mandatory)
* `-m` or `--metadata`: List of csv files containing the data (mandatory)
* `-v` or `--verbose`: Verbose output
* `-o` or `--output`: name of the .nc file generated, by default `out.nc`
* `-k` or `--keep-names`: keep the original coordinate variable names.   

By default, the `generator.py` will convert the coordinate variable names to lower case (e.g. time, depth...). If the
user wants to explicitly retain the source names, the `--keep-names` option can be used. Note that the NetCDF files 
won't be compliant with the EMSO metadata specifications, although it is still possible to create an ERDDAP-compliant 
dataset.


## ⚙️ ERDDAP Configurator ##

The ERDDAP Configurator (`erddap_config.py`) helps prepare ERDDAP dataset definitions for NetCDF files, reducing manual
work editing ERDDAP’s XML configurations. It reads NetCDF metadata and generates ERDDAP dataset configurations. It 
outputs the XML chunk required to register a new dataset. If the `datasets.xml` path is passed, it will automatically 
append or update dataset configuration. 

In order to run the configurator:

To run the 

```bash
python3 erddap_config <nc_file> <dataset_id> <source> 
```
* `nc_file` is the path to a NetCDF to extract its metadata and structure
* `dataset_id`, identifier assigned to the ERDDAP dataset.
* `source` is the path that will be used as the source folder where ERDDAP will scan for NetCDF files ugins the `<fileDir>` option. For more information, check the officcial [ERDDAP documentation](https://erddap.github.io/docs/server-admin/datasets#eddtablefromfilenames-data)

Note that if the ERDDAP server is deployed inside a docker container, the paths inside the container and the paths in the the host will most likely be different. Check the official [docker documentation](https://docs.docker.com/engine/storage/volumes/) on volumes.

### Options:
* `--xml` path to the `datasets.xml`, so the configuration will be directly inserted
* `-v` or `--verbose`: Verbose output
* `-o` or `--output`: store the xml chunk in a file
* `-m` or `--mapping`: provide a mapping file to finetune the dataset source / destination names and attributes.   

The `--mapping` option allows you to create EMSO-compliant dataset from NetCDF files that do not follow the EMSO Metadata
Specifications by specifying the variable name mapping and adding or overloading attribute. Check the examples 
[13](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/13) and [14](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/14) for additional info. 


## 📈 Metadata Report ##

The metadata reporting tool assesses the level of compliance of an ERDDAP or NetCDF dataset with the EMSO Metadata 
Specifications.  

To test an erddap dataset:
```bash
python3 metadata_report.py <target> 
```

where `target` is the path to an ERDDAP dataset or the path to a NetCDF file. If `target` does not directly point to a 
specific dataset, the metadata reporting tool will try to assess all datasets in the server. 

To run the metadata report against an example NetCDF file:
```bash
python3 metadata_report.py examples/01/example01.nc
```


For example, to run the tests on the example 01, the public dataset url can be used:
```bash
python3 metadata_report.py https://netcdf-dev.obsea.es/erddap/tabledap/01.html
```
⚠️ WARNING: when assessing the compliance of the dataset, the metadata reporting tool will download the **whole 
dataset** as a big NetCDF file locally, checking subsets of data is currently not implemented.

The report provides mainly two output, a metadata harmonization score and operational validity. Metadata tests  ensure
that the proper attributes can be found, including variable attributes. The metadata tests provide a harmonization score
as a percentage for required and optional tests. The desired harmonization score is 100% for required tests. 

Operational tests ensure that the dataset is technically sound, it has all the expected coordinates and sensor /
platform metadata is traceable. It provides errors, warning and information messages, but ultimately it 
provides a binary output, whether the dataset is operationally valid or not.

### Options:
* `-v` or `--verbose`: Verbose output
* `-o` or `--output`: store the results as a csv file
* `-i` or `--ignore-ok`: do not successful metadata tests, used to reduce the reports's verbosity
* `-V` or `--variables`: list of variables to test, other variables will be ignored.
* `-c` or `--clear`: clear cached resources, mainly SDN/BODC vocabularies
* `--specs`: Used a local file to read the EMSO Metadata Specifications instead of the public file in github



### Contact info ###

* **author**: Enoc Martínez  
* **version**: v1.0.0-DRAFT    
* **organization**: Universitat Politècnica de Catalunya (UPC)    
* **contact**: enoc.martinez@upc.edu  
