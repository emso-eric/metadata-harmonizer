# Metadata Harmonizer #
This python project contains the tools to connect to an ERDDAP service and assess if the metadata is compliant with the EMSO Metadata Specifications. 

## Setup this project ##
To download this repository:
```bash
$ git clone https://gitlab.emso.eu/Martinez/metadata-harmonizer.git
$ cd metadata-harmonizer
$ pip3 install -r requirements.txt
```
To run the test on an ERDDAP dataset:
```bash
$ python3 metadata_report.py <erddap url>  --list  # get the list of datasets
$ python3 metadata_report.py <erddap url>  -d <dataset_id>  # Run the test for one dataset
```

To run tests on all ERDDAP datasets:
```bash
$ python3 metadata_report.py <erddap url> 
```

### Contact info ###

* **author**: Enoc Martínez
* **version**: v0.1   
* **contributors**: Enoc Martínez 
* **organization**: Universitat Politècnica de Catalunya (UPC)
* **contact**: enoc.martinez@upc.edu