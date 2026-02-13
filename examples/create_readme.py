"""
Automatically generates README files, a general one for the examples folder and an individual README per dataset. The
metadata is automatically processed from the metadata / mapping files
"""
import os
import rich
import numpy as np
import yaml

github_examples = "https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples"
erddap_examples = "https://netcdf-dev.obsea.es/erddap/tabledap"

def get_names_from_mapping(data, var_type):
    """
    Get platform or sensor names from mapping.yaml file
    """
    names = []
    for var in data["mapping"]["variables"]:
        try:
            if var_type == var["attributes"]["variable_type"]:
                names.append(var["attributes"]["long_name"])
        except KeyError:
            continue

    return names



def get_file_list(dir_name):
    """
     create a list of file and sub directories names in the given directory
     :param dir_name: directory name
     :returns: list of all files with relative path
     """
    file_list = os.listdir(dir_name)
    all_files = list()
    for entry in file_list:
        full_path = os.path.join(dir_name, entry)
        if os.path.isdir(full_path):
            all_files = all_files + get_file_list(full_path)
        else:
            all_files.append(full_path)
    return all_files


folders = get_file_list(".")
folders = [os.path.dirname(p) for p in folders]
folders = [f for f in folders if f != "."]
folders = np.unique(folders)
folders = sorted(folders)

examples = []
for folder in folders:
    example = []
    allfiles = get_file_list(folder)
    files = [f for f in allfiles if f.endswith("yaml")]
    ncml = [f for f in allfiles if f.endswith("ncml")]
    csvs = [f for f in allfiles if f.endswith("csv")]
    ncfiles = [f for f in allfiles if f.endswith(".nc")]

    if not files:
        continue

    meta = {}
    for f in files:
        with open(f, "r") as f:
            doc = yaml.safe_load(f)

        meta.update(doc)

    mapping_str = ""
    for f in files:
        if f.endswith("mapping.yaml"):
            mapping_str = f"-m {f}"

    try:
        title = meta["global"]["title"]
        summary = meta["global"]["summary"]
        sensors = [sensor["long_name"] for sensor in meta["sensors"].values()]
        sensors = ", ".join(sensors)
        platforms = ", ".join([p["long_name"] for p in meta["platforms"].values()])
    except KeyError:
        # Getting all data from mapping.yaml
        title = meta["mapping"]["attributes"]["title"]
        summary = meta["mapping"]["attributes"]["summary"]
        platforms = ", ".join(get_names_from_mapping(meta, "platform"))
        sensors = ", ".join(get_names_from_mapping(meta, "sensor"))

    example.append(f"###  {title}  ")
    example.append(f"{summary}  ")
    example.append(f"")
    example.append(f"**sensors**: {sensors}  ")
    example.append(f"**platforms**: {platforms}  ")
    example.append("")

    folder_name = folder.replace("./", "")
    if csvs:
        ncfile = f"example{folder_name}.nc"
    else:
        ncfile = os.path.join("examples", ncfiles[0])

    if "mapping" in meta.keys():
        mapping_str = f"-m examples/{folder}/mapping.yaml "

    keep = ""

    if folder == "./13":
        keep = " --keep"


    if csvs:
        example.append("NetCDF generation command:")
        example.append(f"""```bash
python3 generator.py -m examples/{folder_name}/*.yaml -d examples/{folder_name}/*.csv --out {ncfile} {keep} 
```
""")



    example.append("ERDDAP configuration:")
    folder_name = folder.replace("./", "")
    example.append(f"""```bash
python3 erddap_config.py {ncfile} example{folder_name} /path/to/nc/files {mapping_str}
```
""")

    example.append("")
    example.append("**Additional info**:")
    example.append(f"* 📂 [Explore the source files]({github_examples}/{folder})")
    example.append(f"* 🔗 [ERDDAP dataset]({erddap_examples}/{folder}.html)")



    if mapping_str:
        example.append(
            "* 🔀 This example uses a `mapping.yaml` file to adjust the source / destination names and to override metadata attributes")

    if ncml:
        example.append("* ⚙️ This example uses [NcML](https://docs.unidata.ucar.edu/netcdf-java/current/userguide/ncml_overview.html) to create a virtual dataset in order to add/modify variables on-the-fly without modifying the underlying NetCDF files.")

    if not csvs:
        example.append("* 📦 This example relies on existing NetCDF files! no need to generate new ones  ")

    if keep:
        example.append("* 🔏 This example uses the `--keep` flag to maintain the original upper case coordinate names following Copernicus style")

    # Add new lines and markdown break ('  ')
    example = [line + "  \n" for line in example]

    with open(os.path.join(folder, "README.md"), "w") as f:
        f.writelines(example)

    examples.append(example)

with open("README.md", "w") as f:
    f.writelines(f"""
# EMSO ERIC Dataset Examples \n 
Here you can find an extensive list of examples on how to generate NetCDF datasets and how to integrate them into an ERDDAP server. All the examples in this folder are deployed in the [NetCDF-dev ERDDAP](https://netcdf-dev.obsea.es/erddap/index.html). The configuration of this ERDDAP can be found in [github](https://github.com/emso-eric/example-datasets), including the [datasets.xml](https://github.com/emso-eric/example-datasets/blob/main/conf/datasets.xml) file. 

The commands listed here assume that the user is using a Linux shell or [WSL](https://ubuntu.com/desktop/wsl) and the current directory is the root folder of the metadata harmonizer project and \n 
\n

""")

    for example in examples:
        f.write("\n")
        f.writelines(example)
        f.write("\n")



