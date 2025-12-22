# Metadata Harmonizer Toolbox #
This repository contains a set of tools that can be used to create NetCDF files, integrate them into an ERDDAP server 
and to ensure the compliance with the [EMSO Metadata Specifications](https://github.com/emso-eric/emso-metadata-specifications/tree/develop).
The tools provided here are:
* `generator.py`: creates EMSO-compliant NetCDF files from `.csv` and `.yaml` files  
* `erddap_config.py`: integrates NetCDF files into an ERDDAP server
* `metadata_report.py`: check the compliance of a dataset with the specifications.

## How to use this repository 
This repository tools provided here are intended to create and publish EMSO-compliant datasets. The typical workflow would be:
1. Prepare CSV data and YAML metadata
2. Generate EMSO-compliant NetCDF files using `generator.py`
3. Integrate datasets into your ERDDAP deployment using `erddap_config.py`
4. Validate metadata and operational compliance using `metadata_report.py`

⚠️ WARNING: this work is based on the draft of the new EMSO Metadata Specifications. It has not yet formally approved by the DMSG.  

## 🚀 Project Setup ##
### Prerequisites
Previous requirements are `python 3.8+`,`git` and `pip`. All commands here are for unix-like OS, for Windows users it 
is recommended to use [Ubuntu WSL](https://ubuntu.com/desktop/wsl). If PowerShell or Windows cli is used make sure to change the
unix-like paths (`path/to/file.csv`) to Windows-like paths (`.\path\to\file.csv`).

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
pip3 install -r requirements.txt
```

## 🛠 NetCDF Generator ##

The NetCDF generator creates EMSO-compliant NetCDF datasets from one or more CSV files. The basic workflow is as follows:
1. Encode your **data** as csv files, preferably one file per sensor. Add a `sensor_id` with the identifier of your sensor. Remember to add your QC columns as well 
2. Write the **metadata** for your dataset in one or more yaml files. It should include the following sections `global`, `variables`, `platforms` and `sensors`.
3. Run the `generator.py` script:

```bash 
python3 generator.py -d <csv files> -m <yaml files> --out <NetCDF file>
```
It is strongly recommended to check the [examples folder](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples), where there is a comprehensive list of datasets 
covering different scenarios. For instance, to generate the nc file for the first example:

```bash
python3 generator.py -m examples/01/*.yaml -d examples/01/*.csv --out example01.nc  
```

#### Options:
* `-d` or `--data`: list of csv files containing the data (mandatory)
* `-m` or `--metadata`: list of yaml files containing the metadata (mandatory)
* `-v` or `--verbose`: verbose output
* `-o` or `--output`: name of the .nc file generated, by default `out.nc`
* `-k` or `--keep-names`: keep the original coordinate variable names.   

By default, the `generator.py` will convert the coordinate variable names to lower case (e.g. time, depth...). If the
user wants to explicitly retain the source names, the `--keep-names` option can be used. Note that the NetCDF files 
won't be compliant with the EMSO metadata specifications, although it is still possible to create an ERDDAP-compliant 
dataset if the proper mappings are used (see next section)


## ⚙️ ERDDAP Configurator ##

The ERDDAP Configurator (`erddap_config.py`) helps prepare ERDDAP dataset definitions for NetCDF files, reducing manual
work editing ERDDAP’s XML configurations. It reads NetCDF metadata and generates XML chunk required to register a new 
dataset. If the `datasets.xml` path is passed, it will automatically append or update dataset configuration. 

In order to run the ERDDAP configurator:

```bash
python3 erddap_config <nc_file> <dataset_id> <source> 
```
where:
* `nc_file` is the path to a NetCDF to extract its metadata and structure
* `dataset_id`, identifier assigned to the ERDDAP dataset.
* `source` source folder to scan for `.nc`  files.

The `source` value will be set in the `<fileDir>` option of the dataset configuration. Note that if the ERDDAP server is 
deployed inside a docker container, the paths inside the container and the paths in the host will most likely be 
different. Check the official [docker documentation](https://docs.docker.com/engine/storage/volumes/) on volumes and the  
[ERDDAP documentation](https://erddap.github.io/docs/server-admin/datasets#eddtablefromfilenames-data) 
for more information.



#### Additional Options:
* `--xml` path to the `datasets.xml` to automatically integrate the dataset
* `-v` or `--verbose`: Verbose output
* `-o` or `--output`: store the xml chunk in a file
* `-m` or `--mapping`: provide a mapping file to finetune the dataset source/destination names and attributes.   

The `--mapping` option allows you to create EMSO-compliant dataset from NetCDF files that do not follow the EMSO Metadata
Specifications. This achieved by specifying the source and destination variable names and by adding/overloading 
attributes. Check the examples [13](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/13) and
[14](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/14) for additional info. 


## 📈 Metadata Report ##

The metadata reporting tool assesses the level of compliance of an ERDDAP or NetCDF dataset with the EMSO Metadata 
Specifications. To test a dataset, use the following syntax:
```bash
python3 metadata_report.py <target> 
```
Where `target` is the dataset under test, `.nc` files and ERDDAP dataset URLs are accepted. If `target` points to an ERDDAP 
but no dataset is selected, the metadata reporting tool will assess all datasets in the server. 

To run the metadata report against an example NetCDF file:
```bash
python3 metadata_report.py examples/01/example01.nc
```

To run the same tests for the publicly available ERDDAP dataset:
```bash
python3 metadata_report.py https://netcdf-dev.obsea.es/erddap/tabledap/01.html
```
⚠️ WARNING: when assessing the compliance of the dataset, the metadata reporting tool will download the **whole 
dataset** as a big NetCDF file locally, checking subsets of data is currently not implemented.

The report provides mainly two outputs, a **metadata** harmonization score and its **operational** validity. **Metadata** tests ensure
that the proper attributes can be found, including variable attributes. The metadata tests provide a harmonization score
as a percentage for required and optional tests. The desired harmonization score is 100% for required tests. The score
for optional tests should be taken as qualitative information, since optional fields may not be of interest. 

On the other hand, **operational** tests ensure that the dataset is technically sound, it has all the expected coordinates and sensor /
platform metadata is traceable. It shows errors, warning and information messages, but ultimately it 
provides a binary output, whether the dataset is operationally valid or not.

#### Additional Options:
* `-v` or `--verbose`: Verbose output
* `-o` or `--output`: store the results as a csv file
* `-i` or `--ignore-ok`: do not show successful metadata tests, used to reduce the reports's verbosity
* `-V` or `--variables`: list of variables to test, other variables will be ignored.
* `-c` or `--clear`: clear cached resources, mainly SDN/BODC vocabularies
* `--specs`: Used a local file to read the EMSO Metadata Specifications instead of the public file in github


### Contact info ###

* **author**: Enoc Martínez  
* **version**: v1.0.0-DRAFT    
* **organization**: Universitat Politècnica de Catalunya (UPC)    
* **contact**: enoc.martinez@upc.edu  
