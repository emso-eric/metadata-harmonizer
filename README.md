# Metadata Harmonizer #
This python project contains the tools to connect to an ERDDAP service and assess if the metadata is compliant with the EMSO Metadata Specifications.
This project can be used as a standalone cli tool or as a [PyPi](https://pypi.org/project/emso-metadata-harmonizer) package to be integrated with other code.

## Setup this project ##
To download this repository:
```bash
$ git clone https://github.com/emso-eric/metadata-harmonizer
$ cd metadata-harmonizer
$ pip3 install -r requirements.txt
```

## Metadata Tester ##
Test o run the test on an ERDDAP dataset:

The `metadata_report.py` tool tests if the metadata contained within a dataset (ERDDAP, NetCDF or JSON) is compatible with EMSO Metadata Specifications.

To test an erddap dataset:
```bash
$ python3 metadata_report.py <erddap url>  --list  # get the list of datasets
$ python3 metadata_report.py <erddap url>  -d <dataset_id>  # Run the test for one dataset
```

For example, to run tests on dataset with id=```EMSO_Western_Ionian_Sea_CTD_2002_2003``` from EMSO's central ERDDAP:
```bash
$ python3 metadata_report.py https://erddap.emso.eu  -d EMSO_Western_Ionian_Sea_CTD_2002_2003
```

    
To run tests on all ERDDAP datasets:
```bash
$ python3 metadata_report.py <erddap url> 
```
To run tests on a NetCDF file
```bash
$ python3 metadata_report.py <filename> 
```

## Dataset Generator ##
The `generator.py` tool allows to create EMSO-compliant NetCDF files.

#### Creating a Dataset based on CSV files ####
To create a NetCDF file from a CSV file, the first step is to generate the minimal metadata template (`.min.json`) based on the CSV file structure. To generate the template use the following command:  

```bash
$ python3 generator.py --data <filename> --generate <folder> 
```

A minimal metadata template (`.min.json`) file will be created within the folder. Then, it is required to add the metadata within the minimal metadata template. All attributes with a leading `*` (e.g. `*title`) are mandatory. Attributes with a leading `~` are optional. If not filled, they will be deduced from default values or other parameters. Fields with a leadig `$` will be asked interactively. Once the minimal metadata template is filled we are ready to generate the NetCDF dataset:

```bash
$ python3 generator.py --data <filename> --metadata <minimal metadata>  --outfile <output nc file> 
```
When executing the generator with the `--metadata` option, the minimal metadata template will be expand the metadata and add all default values and derived attributes. The minimal metadata template will be updated with the user choices and derived options. Additionally, a full metadata file (`.full.json`) will be generated and stored alongside the minimal metadata template. The data from the CSV file and the generated metadata will be combined into the NetCDF file espcified with the `--outfile` option.

If some of the default values or derived attributes need to be modified it is possible to modify the full metadata file (`.full.json`) and re-run the generator:
```bash
$ python3 generator.py --data <filename> --metadata <full metadata>  --outfile <output nc file> 
```

The changes in the full metadata file will be reflected on the output nc file.

### Creating a Dataset based on multiple CSV files ###

Several CSV files can be comined into a single NetCDF file. Assuming that we want combine data1.csv and data2.csv into a single NetCDF file: 

```bash
# Creates minimal metadata templates data1.min.json and data2.min.json
$ python3 generator.py --data data1.csv data2.csv --generate myfolder

# Edit the minimal metadata files and rerun the generator with the --metadata option
$ python3 generator.py --data data1.csv data2.csv -m myfolder/data1.min.json myfolder/data2.min.json -o all.nc
```

Now the data from both files is combined into the `all.nc` file. Note that there is some metadata overlapping in the data1.min.json and data2.min.json. In case of a conflicting attribute the values in the leftmost file will prevail.


### Contact info ###

* **author**: Enoc Martínez  
* **version**: v0.4.6    
* **organization**: Universitat Politècnica de Catalunya (UPC)    
* **contact**: enoc.martinez@upc.edu  
