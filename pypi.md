# Metadata Harmonizer Toolbox #
This repository contains a set of tools that can be used to create NetCDF files, integrate them into an ERDDAP server 
and to ensure the compliance with the [EMSO Metadata Specifications](https://github.com/emso-eric/emso-metadata-specifications/tree/develop). 
The tools provided here are:
* `emh.generate_dataset()`: creates EMSO-compliant NetCDF files from `.csv` and `.yaml` files  
* `emh.erddap_config()`: integrates NetCDF files into an ERDDAP server
* `emh.metadata_report()`: check the compliance of a dataset with the specifications.

In order to  create and publish an EMSO-compliant dataset, the typical workflow is:
1. Prepare CSV data and YAML metadata
2. Generate EMSO-compliant NetCDF files using `generate_dataset()`
3. Integrate datasets into your ERDDAP deployment using `erddap_config()`
4. Validate metadata and operational compliance using `metadata_report()`


## Installation
To install as a PyPi package:
```bash
pip3 install emso_metadata_harmonizer
```

## 🛠 NetCDF Generator ##

To generate a NetCDF dataset from data (csv) and metadata (yaml) files: 

```python3
import emso_metadata_harmonizer as emh

emh.generate_dataset(["data.csv"], ["meta.yaml"], output="dataset.nc")
```

Full example with data and metadata from the [example 2](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples/02)

```python3
import emso_metadata_harmonizer as emh
import urllib

# Download data and metadata from the example 2 in the metadata-harmonizer repository
data_url = "https://raw.githubusercontent.com/emso-eric/metadata-harmonizer/refs/heads/develop/examples/02/SBE16.csv"
meta_url = "https://raw.githubusercontent.com/emso-eric/metadata-harmonizer/refs/heads/develop/examples/02/meta.yaml"
urllib.request.urlretrieve(data_url, "data.csv")
urllib.request.urlretrieve(meta_url, "meta.yaml")

# Generate dataset from one data file
emh.generate_dataset(["data.csv"], ["meta.yaml"], "dataset.nc")
```

To generate a dataset from multiple data files:
```python3
import emso_metadata_harmonizer as emh
import urllib

# Generate dataset from multiple data files
data1_url = "https://raw.githubusercontent.com/emso-eric/metadata-harmonizer/refs/heads/develop/examples/02/SBE16.csv"
data2_url = "https://raw.githubusercontent.com/emso-eric/metadata-harmonizer/refs/heads/develop/examples/02/SBE37.csv"
meta_url = "https://raw.githubusercontent.com/emso-eric/metadata-harmonizer/refs/heads/develop/examples/02/meta.yaml"
urllib.request.urlretrieve(data1_url, "data1.csv")
urllib.request.urlretrieve(data2_url, "data2.csv")
urllib.request.urlretrieve(meta_url, "meta.yaml")

emh.generate_dataset(["data.csv", "data2.csv"], ["meta.yaml"], "dataset2.nc")

```

## ⚙️ ERDDAP Configurator ##

The ERDDAP Configurator (`erddap_config()`) helps prepare ERDDAP dataset definitions for NetCDF files, reducing manual
work editing ERDDAP’s XML configurations. It reads NetCDF metadata and generates XML chunk required to register a new 
dataset.  

```python3
import emso_metadata_harmonizer as emh

emh.erddap_config("dataset2.nc", "MyDatasetIdentifier", "/path/to/dataset/files")
```

To automatically append a new dataset into an existing ERDDAP deployment, the path to the `datasets.xml` file should
be passed via the `datasets_xml_file` parameter.

```python3
import emso_metadata_harmonizer as emh

emh.erddap_config("dataset.nc", "MyDatasetIdentifier", "/path/to/dataset/files", datasets_xml_file="path/to/datasets.xml")
```


## 📈 Metadata Report ##

The metadata reporting tool assesses the level of compliance of an ERDDAP or NetCDF dataset with the EMSO Metadata 
Specifications. To test a dataset, use the following syntax:

```python3
import emso_metadata_harmonizer as emh
emh.metadata_report("dataset.nc")
```

### Contact info ###

* **author**: Enoc Martínez  
* **version**: v1.0.0    
* **organization**: Universitat Politècnica de Catalunya (UPC)    
* **contact**: enoc.martinez@upc.edu  
