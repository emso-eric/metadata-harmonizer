import pandas as pd
import numpy as np
import rich
import os
import yaml


def to_csv(df, folder, name):
    filename = os.path.join(folder, name)
    df["time"] = pd.to_datetime(df["time"])
    df["time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df.to_csv(filename, index=False, float_format="%.4f")


def create_info(info: dict, folder):
    os.makedirs(folder, exist_ok=True)
    rich.print(f"[cyan]Creating {folder}")
    rich.print(f"    title: {info['title']}")

    with open(os.path.join(folder, "README.yaml"), "w") as f:
        yaml.dump(info, f)


def guess_command(folder):
    files = [os.path.join("examples", folder, f) for f in os.listdir(folder)]
    files = sorted(files)
    csv_files = [f for f in files if f.endswith(".csv")]
    min_meta = [f for f in files if f.endswith(".min.json")]
    output = os.path.join("examples", folder, folder + ".nc")
    rich.print(f"[grey42]python3 generator.py  --data {' '.join(csv_files)} --metadata {' '.join(min_meta)} --output {output}")


# Time variable and time vector
times = pd.date_range("2024-01-01", "2025-01-01", freq="30min")
t = np.arange(0, len(times))/len(times)

# ============ Example 1: A single CTD ============ #
info = {
    "title": "Fixed-point CTD data",
    "comment": "simple dataset with only one CTD at a fixed depth",
    "sensors": ["SBE37 (CTD) deployed at 20m depth"],
    "CF_featureType": "timeSeries"
}
folder = "example01"
create_info(info, folder)

# data variables
temp = 20 + 8 * np.sin(2*np.pi*t)
cndc = 5 + np.sin(2*np.pi*t)
pres = 20 + 2 * np.sin(365*2*np.pi*t)

qc_flags = np.zeros(len(t)).astype(np.int8) + 1

df = pd.DataFrame({
    "time": times,
    "TEMP": temp, "TEMP_QC": qc_flags,
    "CNDC": cndc, "CNDC_QC": qc_flags,
    "PSAL": temp, "PSAL_QC": qc_flags
})
to_csv(df, folder, "SBE37.csv")
guess_command(folder)


# ============ Example 2: Two CTDs at different depths ============ #
info = {
    "title": "Two CTDs at different depths",
    "comment": "dataset with two CTDs deployed at different depths",
    "sensors": ["SBE16 (CTD) deployed at 10m depth", "SBE37 (CTD) deployed at 20m depth"],
    "CF_featureType": "timeSeries"
}
folder = "example02"
create_info(info, folder)

temp1 = 20 + 8 * np.sin(2*np.pi*t)
cndc1 = 5 + np.sin(2*np.pi*t)
pres1 = 10 + 2 * np.sin(365*2*np.pi*t)

temp2 = 15 + 5 * np.sin(2*np.pi*t)
cndc2 = 4.5 + np.sin(2*np.pi*t)
pres2 = 20 + 2 * np.sin(365*2*np.pi*t)

df1 = pd.DataFrame({
    "time": times,
    "TEMP": temp1, "TEMP_QC": qc_flags,
    "CNDC": cndc1, "CNDC_QC": qc_flags,
    "PSAL": temp1, "PSAL_QC": qc_flags
})

df2 = pd.DataFrame({
    "time": times,
    "TEMP": temp2, "TEMP_QC": qc_flags,
    "CNDC": cndc2, "CNDC_QC": qc_flags,
    "PSAL": pres2, "PSAL_QC": qc_flags
})
to_csv(df1, folder, "SBE16.csv")
to_csv(df2, folder, "SBE37.csv")
guess_command(folder)

# ============ Example 3: Two CTDs at same depth ============ #
info = {
    "title": "Two CTDs swapped by time",
    "comment": "Two CTDs that are deployed in the same place at different times. Common scenario when an instrument is swapped for maintenance",
    "sensors": ["SBE16 (CTD) deployed at 20m depth from January to July", "SBE37 (CTD) deployed at 20m depth from July to December"],
    "CF_featureType": "timeSeries"
}
folder = "example03"
create_info(info, folder)

times1 = pd.date_range("2024-01-01T00:00:00Z", "2024-06-30T23:30:00Z", freq="30min")
times2 = pd.date_range("2024-07-01T00:00:00Z", "2024-12-31T23:30:00Z", freq="30min")
t1 = np.arange(0, len(times1)) / len(times1)
t2 = np.arange(0, len(times2)) / len(times2)

temp1 = 20 + 8 * np.sin(2*np.pi*t1)
cndc1 = 5 + np.sin(2*np.pi*t1)
pres1 = 10 + 2 * np.sin(365*2*np.pi*t1)

temp2 = 15 + 5 * np.sin(2*np.pi*t2)
cndc2 = 4.5 + np.sin(2*np.pi*t2)
pres2 = 20 + 2 * np.sin(365*2*np.pi*t2)

qc_flags1 = np.zeros(len(t1)) + 1
qc_flags2 = np.zeros(len(t2)) + 1

df1 = pd.DataFrame({
    "time": times1,
    "TEMP": temp1, "TEMP_QC": qc_flags1,
    "CNDC": cndc1, "CNDC_QC": qc_flags1,
    "PSAL": temp1, "PSAL_QC": qc_flags1
})

df2 = pd.DataFrame({
    "time": times2,
    "TEMP": temp2, "TEMP_QC": qc_flags2,
    "CNDC": cndc2, "CNDC_QC": qc_flags2,
    "PSAL": temp2, "PSAL_QC": qc_flags2
})

to_csv(df1, folder, "SBE16.csv")
to_csv(df2, folder, "SBE37.csv")
guess_command(folder)
