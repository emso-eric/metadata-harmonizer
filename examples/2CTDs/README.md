# 2 CTDs dataset #

This folder contains an example on how to generate a dataset based on two CSV files containing data from two CTDs at OBSEA: `SBE16.csv` and `SBE37.csv`. 

#### Step 1. Generating minimal metadata templates ####

The first step is to run the generator.py to create the metadata templates. Assuming that we are on the root of the project:

> $ python3 generator.py --data examples/2CTDs/SBE16.csv examples/2CTDs/SBE37.csv --generate examples/2CTDs

The `--data` attribute provides a list of data files to be processed. The `--generate` states the folder where the metadata templates will be generated.

After running the command, two minimal metadata template files will appear in the `examples/2CTDs` folder: `SBE16.min.json` and `SBE37.min.json`.

#### Step 2. Fill the metadata ####
Now it's time to include the metadata into the `min.json` files. Let's start with filling the global metadata. As stated in the header of the `min.json` files it is only needed to explicitly fill those attributes with a leading `*` such as `*title`. The following metadata can be copy-pasted into the global section of the generated `SBE16.min.json` and `SBE37.min.json` files. 

```json
{
  "global": {
    "*title": "CTD data at OBSEA from 2021-01-01 to 2022-01-01",
    "*summary": "CTD data at the OBSEA Underwater Observatory, located at the Catalan coast (NW Mediterranean sea) at at depth of 20 meters from 2011 to 2023",
    "~Conventions": "",
    "*institution_edmo_code": "2150",
    "~update_interval": "void",
    "$site_code": "",
    "$emso_facility": "",
    "*source": "mooring",
    "$data_type": "",
    "~format_version": "",
    "~network": "",
    "$data_mode": "",
    "project": "",
    "*principal_investigator": "Joaquin del Rio",
    "*principal_investigator_email": "joaquin.del.rio@upc.edu",
    "~license": ""
  }
}
```
Then we can move to the variable metadata. In this section we need to specify what is measured. The following section can be copy-pasted into the variables section of `SBE16.min.json` an  `SBE37.min.json` files.

```json
{
  "variables": {
    "TEMP": {
      "*long_name": "sea water temperature at OBSEA",
      "*sdn_parameter_uri": "http://vocab.nerc.ac.uk/collection/P01/current/TEMPST01",
      "~sdn_uom_uri": "",
      "~standard_name": ""
    },
    "PRES": {
      "*long_name": "sea water pressure at OBSEA",
      "*sdn_parameter_uri": "http://vocab.nerc.ac.uk/collection/P01/current/PRESPR01",
      "~sdn_uom_uri": "",
      "~standard_name": ""
    },
    "CNDC": {
      "*long_name": "sea water electrical condcuvtiviy at OBSEA",
      "*sdn_parameter_uri": "http://vocab.nerc.ac.uk/collection/P01/current/CNDCST01",
      "~sdn_uom_uri": "",
      "~standard_name": ""
    },
    "PSAL": {
      "*long_name": "sea water salinity at OBSEA",
      "*sdn_parameter_uri": "http://vocab.nerc.ac.uk/collection/P01/current/PRESPR01",
      "~sdn_uom_uri": "",
      "~standard_name": ""
    },
    "SVEL": {
      "*long_name": "speed of sound in sea water at OBSEA",
      "*sdn_parameter_uri": "http://vocab.nerc.ac.uk/collection/P01/current/SVELCT01",
      "~sdn_uom_uri": "",
      "~standard_name": ""
    }
  }
}
```

Then we need to add the sensor metadata. The following info can be copy-pasted into the `sensor` section for the `SBE16.min.json`

```json
{
  "sensor": {
    "*sensor_model_uri": "https://vocab.nerc.ac.uk/collection/L22/current/TOOL0870",
    "*sensor_serial_number": "16P57353-6479",
    "$sensor_mount": "",
    "$sensor_orientation": ""
  }
}
```

And the same the SBE37 CTD. The following info can be copy-pasted into the `sensor` section for the `SBE37.min.json`
```json
{
    "*sensor_model_uri": "https://vocab.nerc.ac.uk/collection/L22/current/TOOL1457",
    "*sensor_serial_number": "37SMP47472-5496",
    "$sensor_mount": "",
    "$sensor_orientation": ""
}
```

Finally, we need to add the coordinates of the deployment. In both cases they have the same position. The following info can be copy-pasted to both  `SBE16.min.json` an  `SBE37.min.json` files.
```json
{
  "coordinates": {
    "README": "If the dataset has fixed coordinates, please add them here as floats",
    "depth": 20,
    "latitude": 41.18212,
    "longitude": 1.75257
  }
}
```

#### Step 3. Generate the Dataset ####

Now that we have added the metadata into the minimal metadata templates, we can generate a dataset merging both data files. Note that in our metadata files there are a lot of missing fields, however they all will be eventually derived from other metadata or the user will be required to input them from a list. All fields starting with `~` will be derived from other info, e.g. the units will  befilled with the default value from the `sdn_parameter_uri`. All attributes starting with `$` will be asked interactively to the user.

To generate a NetCDF dataset run the following command:

> $ python3 generator.py --data examples/2CTDs/SBE16.csv examples/2CTDs/SBE37.csv --metadata examples/2CTDs/SBE16.min.json examples/2CTDs/SBE16.min.json --output dataset.nc

After running the command and providing all the input required by the script, all your inputs will be reflected on the `SBE16.min.json` and `SBE37.min.json`. If you re-run the script note that it won't ask again for input, since all the data is already present in the minimal metadata template files.

With the previous command we passed two CSV data files to the generator and two minimal metadata files. The leftmost metadata file (`SBE16.min.json` in the example) has the higher priority. This means that if a global metadata attribute has different values (e.g. `*title`), the title in the leftmost file will be stored in the resulting NetCDF file.

#### Step 4. Metadata fine-tuning (optional)####

In the previous step, in addition to the output NetCDF file, two extensive metadata document have been created: `SBE16.full.json` and `SBE37.full.json`. This documents contain all the metadata that is included in the  output NetCDF dataset. Note that a lot of information has been automatically filled based on BODC vocabularies default relations, e.g. preferred units. In case this metadata needs to be fine-tuned, it is possible to manually edit the `full.json` metadata files and then re-generate the NetCDF dataset. To do so, instead use the same command but with the `.full.json` files within the  `--metadata` option:  

> $ python3 generator.py --data examples/2CTDs/SBE16.csv examples/2CTDs/SBE37.csv --metadata examples/2CTDs/SBE16.full.json examples/2CTDs/SBE16.full.json --output dataset.nc

#### Step 5. Adding the dataset to ERDDAP ####
Once we have a nice NetCDF file with all our data and metadata, it is time to include it into an ERDDAP service. To add a NetCDF dataset into an ERDDAP we need to define a new dataset within the `datasets.xml` ERDDAP file. Writing this file manually is often complex and error-prone, but within this repository there is an automated tool for the integration of datasets into ERDDAP, the `erddap_config.py` script.

Three arguments are requried, the NetCDF dataset, an id for the dataset and the path to the folder containing your NetCDF files. This tools provides two ways to integrate a dataset, the first is by generating the XML configuration chunk and copy-pasting it to your `datasets.xml` config file: 

> $ python3 erddap_config.py dataset.nc MyDatasetID /path/to/my/folder

If no additional option are set, the XML chunk will be printed into the screen. However, the output can also be stored in a xml file:

> $ python3 erddap_config.py dataset.nc MyDatasetID /path/to/my/folder --output chunk.xml

It also possible to let the script to automatically modify your `datasets.xml` file:

> $ python3 erddap_config.py dataset.nc MyDatasetID /path/to/my/folder --xml /path/to/datasets.xml

Note that the current configuration file is backed up into a hidden file with the pattern `<your_path>/.datasets.xml.<timestamp>`. In case something goes wrong you can always rollback to the previous version.

Now you can restart your ERDDAP service and the new dataset should appear.