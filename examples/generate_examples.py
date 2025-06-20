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
    min_meta = [f for f in files if f.endswith(".yaml")]
    output = os.path.join("examples", folder, "example" + folder + ".nc")
    rich.print(f"[grey42]python3 generator.py  --data {' '.join(csv_files)} --metadata {' '.join(min_meta)} --output {output}")



# ============ Example 1: A single CTD ============ #

folder = "01"

# Time variable and time vector
times = pd.date_range("2024-01-01", "2025-01-01", freq="30min")
t = np.arange(0, len(times))/len(times)


# data variables
temp = 20 + 8 * np.sin(2*np.pi*t)
cndc = 5 + np.sin(2*np.pi*t)
pres = 20 + 2 * np.sin(365*2*np.pi*t)
psal = 36 + 2 * np.sin(365*2*np.pi*t)


df = pd.DataFrame({
    "time": times,
    "depth": np.zeros(len(times)) + 20,
    "TEMP": temp, "TEMP_QC": 1,
    "CNDC": cndc, "CNDC_QC": 1,
    "PRES": pres, "PRES_QC": 1,
    "PSAL": psal, "PSAL_QC": 1,
})
to_csv(df, folder, "SBE37.csv")
guess_command(folder)


# ============ Example 2: Two CTDs at different depths ============ #

folder = "02"

temp1 = 20 + 5 * np.sin(2*np.pi*t)
cndc1 = 5 + np.sin(2*np.pi*t)
psal1 = 37 + np.sin(2*np.pi*t)
pres1 = 10 + 2 * np.sin(365*2*np.pi*t)

temp2 = 15 + 5 * np.sin(2*np.pi*t)
cndc2 = 5 + np.sin(2*np.pi*t)
psal2 = 36 + np.sin(2*np.pi*t)
pres2 = 20 + 2 * np.sin(365*2*np.pi*t)

df1 = pd.DataFrame({
    "time": times,
    "depth": 10.0,
    "sensor_id": "SBE16_SN57353_6479",
    "TEMP": temp1, "TEMP_QC": 1,
    "CNDC": cndc1, "CNDC_QC": 1,
    "PSAL": psal1, "PSAL_QC": 1,
    "PRES": pres1, "PRES_QC": 1
})

df2 = pd.DataFrame({
    "time": times,
    "depth": 20.0,
    "sensor_id": "SBE37SMP_SN47472_5496",
    "TEMP": temp2, "TEMP_QC": 1,
    "CNDC": cndc2, "CNDC_QC": 1,
    "PSAL": psal2, "PSAL_QC": 1,
    "PRES": pres2, "PRES_QC": 1
})


to_csv(df1, folder, "SBE16.csv")
to_csv(df2, folder, "SBE37.csv")
guess_command(folder)

# ============ Example 3: Two CTDs at same depth ============ #
folder = "03"

times1 = pd.date_range("2024-01-01T00:00:00Z", "2024-06-30T23:30:00Z", freq="30min")
times2 = pd.date_range("2024-07-01T00:00:00Z", "2024-12-31T23:30:00Z", freq="30min")
t1 = np.arange(0, len(times1)) / len(times1)
t2 = np.arange(0, len(times2)) / len(times2)

temp1 = 20 + 8 * np.sin(2*np.pi*t1)
cndc1 = 5 + np.sin(2*np.pi*t1)
pres1 = 10 + 2 * np.sin(365*2*np.pi*t1)
psal1 = 36 + 2 * np.sin(2*np.pi*t1)

temp2 = 20 + 5 * np.sin(2*np.pi*t2)
cndc2 = 5 + np.sin(2*np.pi*t2)
pres2 = 20 + 2 * np.sin(365*2*np.pi*t2)
psal2 = 34 + 2 * np.sin(2*np.pi*t2)


df1 = pd.DataFrame({
    "time": times1,
    "depth": 20.0,
    "sensor_id": "SBE37SMP_SN47472_5496",
    "TEMP": temp1, "TEMP_QC": 1,
    "CNDC": cndc1, "CNDC_QC": 1,
    "PRES": pres1, "PRES_QC": 1,
    "PSAL": temp1, "PSAL_QC": 1
})

df2 = pd.DataFrame({
    "time": times2,
    "depth": 20.0,
    "sensor_id": "SBE16_SN57353_6479",
    "TEMP": temp2, "TEMP_QC": 1,
    "CNDC": cndc2, "CNDC_QC": 1,
    "PRES": pres2, "PRES_QC": 1,
    "PSAL": psal2, "PSAL_QC": 1
})

to_csv(df1, folder, "SBE37.csv")
to_csv(df2, folder, "SBE16.csv")
guess_command(folder)

# ============ Example 4: 4 CTDs at different depths + surface weather station ============ #

folder = "04"

times1 = pd.date_range("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z", freq="30min")


t1 = np.arange(0, len(times1)) / len(times1)

temp1 = 25 + 5 * np.sin(2*np.pi*t1)
cndc1 = 5 + np.sin(2*np.pi*t1)
pres1 = 100 + 2 * np.sin(365*2*np.pi*t1)
psal1 = 36 + 1 * np.sin(2*np.pi*t1)

temp2 = 20 + 5 * np.sin(2*np.pi*t1)
cndc2 = 4 + np.sin(2*np.pi*t1)
pres2 = 200 + 2 * np.sin(365*2*np.pi*t1)
psal2 = 36 + 1 * np.sin(2*np.pi*t1)

temp3 = 15 + 5 * np.sin(2*np.pi*t1)
cndc3 = 3 + np.sin(2*np.pi*t1)
pres3 = 300 + 2 * np.sin(365*2*np.pi*t1)
psal3 = 36 + 1 * np.sin(2*np.pi*t1)

temp4 = 10 + 5 * np.sin(2*np.pi*t1)
cndc4 = 2 + np.sin(2*np.pi*t1)
pres4 = 400 + 2 * np.sin(365*2*np.pi*t1)
psal4 = 36 + 1 * np.sin(2*np.pi*t1)

data = [
    (100, temp1, cndc1, pres1, psal1),
    (200, temp2, cndc2, pres2, psal2),
    (300, temp3, cndc3, pres3, psal3),
    (400, temp4, cndc4, pres4, psal4)
]

for (depth, temp, cndc, pres, psal) in data:
    df = pd.DataFrame({
        "time": times1,
        "depth": depth,
        "sensor_id": f"SBE37SMP_{depth}",
        "TEMP": temp, "TEMP_QC": 1,
        "CNDC": cndc, "CNDC_QC": 1,
        "PRES": temp, "PRES_QC": 1,
        "PSAL": temp, "PRES_QC": 1
    })
    to_csv(df, folder, f"SBE37_{depth}m.csv")

# Create weather station with another time frame
times2 = pd.date_range("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z", freq="47min")
t2 = np.arange(0, len(times2)) / len(times2)

airt = 30 + 10 * np.sin(2*np.pi*t2)
wspd = 10 + np.sin(2*np.pi*t2)
wdir = 180 + 180 * np.sin(5*2*np.pi*t2)

df = pd.DataFrame({
    "time": times2,
    "depth": -1,
    "sensor_id": "Airmar_200WX_SN0001",
    "AIRT": airt, "WSPD": wspd, "WDIR": wdir,
    "AIRT_QC": 1, "WSPD_QC": 1, "WDIR_QC": 1
})
to_csv(df, folder, "AimarWeatherStation.csv")

guess_command(folder)


# ============ Example 5: Several deployments of the same mooring ============ #
# Create data for 3 deployments at the same place. lat/lon will vary slightly. Sensors in the mooring will be swapped from
# deployment to deployment

folder = "05"

# Create 3 different deployments, for 2022, 2023 and 2024. Vary lat/lon slightly
times1 = pd.date_range("2022-01-01T00:00:00Z", "2022-12-30T23:59:59Z", freq="30min")
times2 = pd.date_range("2023-01-01T00:00:00Z", "2023-12-30T23:59:59Z", freq="30min")
times3 = pd.date_range("2024-01-01T00:00:00Z", "2024-12-30T23:59:59Z", freq="30min")

deployments = (
    (times1, 43.8419, 9.1339, {100: "SBE37SMP_SN0001", 200: "SBE37SMP_SN0002", 300: "SBE37SMP_SN0003", 400: "SBE37SMP_SN0004"}),
    (times2, 43.8423, 9.1350, {100: "SBE37SMP_SN0004", 200: "SBE37SMP_SN0003", 300: "SBE37SMP_SN0002", 400: "SBE37SMP_SN0001"}),
    (times3, 43.8401, 9.1317, {100: "SBE37SMP_SN0002", 200: "SBE37SMP_SN0004", 300: "SBE37SMP_SN0001", 400: "SBE37SMP_SN0003"})
)

for times, lat, lon, sensors in deployments:

    t = np.arange(0, len(times)) / len(times)
    year = times[0].strftime("%Y")
    for depth, sensor_id in sensors.items():
        # the deeper, less salinity and less temperature
        temp = 30 - (depth/25) + 5 * np.sin(2*np.pi*t)
        cndc =  6 - (depth/100) + np.sin(2*np.pi*t)
        pres = depth + 2 * np.sin(365*2*np.pi*t)
        psal = 3 - (depth/100) + np.sin(365*2*np.pi*t)

        df = pd.DataFrame({
            "time": times,
            "depth": depth,
            "sensor_id": sensor_id,
            "precise_latitude": lat,
            "precise_longitude": lon,
            "TEMP": temp, "TEMP_QC": 1,
            "CNDC": cndc, "CNDC_QC": 1,
            "PRES": temp, "PRES_QC": 1,
            "PSAL": psal, "PSAL_QC": 1
        })
        to_csv(df, folder, f"{sensor_id}_depth_{depth}m_{year}.csv")
    airt = 30 + 10 * np.sin(2 * np.pi * t)
    wspd = 10 + np.sin(2 * np.pi * t)
    wdir = 180 + 180 * np.sin(5 * 2 * np.pi * t)


    df = pd.DataFrame({
        "time": times,
        "precise_latitude": lat,
        "precise_longitude": lon,
        "depth": -1,
        "sensor_id": "Airmar_200WX_SN0001",
        "AIRT": airt, "WSPD": wspd, "WDIR": wdir,
        "AIRT_QC": 1, "WSPD_QC": 1, "WDIR_QC": 1
    })
    to_csv(df, folder, f"AimarWeatherStation_{year}.csv")

guess_command(folder)


# ============ Example 6: Current Profile with an ADCP  ============ #
folder = "06"

times1 = pd.date_range("2024-01-01T00:00:00Z", "2024-12-31T23:59:00Z", freq="30min")
t1 = np.arange(0, len(times1)) / len(times1)

array_by_depth = []

for depth in range(10, 101, 10):
    cspd = np.abs(3 * np.sin(2*np.pi*t1  +  depth/100*2*np.pi))
    cdir = 180 + 180 * np.sin(2*np.pi*t1  +  depth/100*2*np.pi)
    array_by_depth.append((depth, cspd, cdir))

dataframes = []
for depth, cspd, cdir in array_by_depth:
    df = pd.DataFrame({
        "time": times1,
        "depth": np.zeros(len(t1)) + depth,
        "CSPD": cspd,
        "CDIR": cdir,
        "CSPD_QC": 1,
        "CDIR_QC": 1
    })
    dataframes.append(df)

df = pd.concat(dataframes)

to_csv(df, folder, "AWAC.csv")
guess_command(folder)


# ============ Example 7: Two ADCPs at different depths  ============ #
folder = "07"
times1 = pd.date_range("2024-01-01T00:00:00Z", "2024-12-31T23:59:00Z", freq="30min")
t1 = np.arange(0, len(times1)) / len(times1)

array_by_depth = []

for depth in range(10, 101, 10):
    cspd = np.abs(3 * np.sin(2*np.pi*t1  +  depth/100*2*np.pi))
    cdir = 180 + 180 * np.sin(2*np.pi*t1  +  depth/100*2*np.pi)
    array_by_depth.append((depth, cspd, cdir))

dataframes = []
for depth, cspd, cdir in array_by_depth:
    df = pd.DataFrame({
        "time": times1,
        "depth": np.zeros(len(t1)) + depth,
        "CSPD": cspd,
        "CDIR": cdir,
        "CSPD_QC": 1,
        "CDIR_QC": 1

    })
    dataframes.append(df)

df = pd.concat(dataframes)
df["sensor_id"] = "AWAC_SN0001"
to_csv(df, folder, "AWAC_AST_1.csv")
df["depth"] = df["depth"] + 100
df["sensor_id"] = "AWAC_SN0002"
to_csv(df, folder, "AWAC_AST_2.csv")

guess_command(folder)

# ============ Example 8: CTD in a AUV  ============ #
folder = "08"

# Time variable and time vector
times = pd.date_range("2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z", freq="1min")
t = np.arange(0, len(times))/len(times)

# data variables
# 41.205286885526746, 1.729306054662221
temp = 20 + 8 * np.sin(2*np.pi*t)
cndc = 5 + np.sin(2*np.pi*t)
pres = 4 + np.sin(10*2*np.pi*t)
psal = 36 + np.sin(10*2*np.pi*t)
depth = pres
latitude = 41.206253  - 0.1*t - 0.01*np.sin(10*2*np.pi*t)
longitude = 1.7324103 + 0.1*t # + np.abs(np.sin(10*2*np.pi*t))


df = pd.DataFrame({
    "time": times,
    "depth": depth,
    "latitude": latitude,
    "longitude": longitude,
    "TEMP": temp, "TEMP_QC": 1,
    "CNDC": cndc, "CNDC_QC": 1,
    "PRES": pres, "PRES_QC": 1,
    "PSAL": psal, "PSAL_QC": 1
})
to_csv(df, folder, "AUV_data.csv")
guess_command(folder)


# ============ Example 9: Two AUVs with CTDs  ============ #

folder = "09"

# Time variable and time vector
times = pd.date_range("2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z", freq="1min")
t = np.arange(0, len(times))/len(times)

# data variables
# 41.205286885526746, 1.729306054662221
temp = 20 + 8 * np.sin(2*np.pi*t)
cndc = 5 + np.sin(2*np.pi*t)
pres = 4 + np.sin(10*2*np.pi*t)
psal = 36 + np.sin(10*2*np.pi*t)

depth = pres
latitude = 41.206253  - 0.1*t - 0.01*np.sin(10*2*np.pi*t)
longitude = 1.7324103 + 0.1*t # + np.abs(np.sin(10*2*np.pi*t))

df = pd.DataFrame({
    "time": times,
    "depth": depth,
    "latitude": latitude,
    "longitude": longitude,
    "platform_id": "Girona500_SN0002",
    "sensor_id": "SBE37SMP_SN47472_5496",
    "TEMP": temp, "TEMP_QC": 1,
    "CNDC": cndc, "CNDC_QC": 1,
    "PRES": pres, "PRES_QC": 1,
    "PSAL": psal, "PSAL_QC": 1

})
to_csv(df, folder, "AUV_SN0001.csv")

times = pd.date_range("2024-01-01T00:10:00Z", "2024-01-02T00:10:00Z", freq="90s")
t = np.arange(0, len(times))/len(times)

# data variables
# 41.205286885526746, 1.729306054662221
temp = 20 + 8 * np.sin(2*np.pi*t)
cndc = 5 + np.sin(2*np.pi*t)
pres = 4 + np.sin(10*2*np.pi*t)
psal = 36 + np.sin(10*2*np.pi*t)

depth = pres
latitude = 41.106253  - 0.1*t - 0.01*np.sin(10*2*np.pi*t)
longitude = 1.7224103 + 0.1*t # + np.abs(np.sin(10*2*np.pi*t))

df = pd.DataFrame({
    "time": times,
    "depth": depth,
    "latitude": latitude,
    "longitude": longitude,
    "platform_id": "Sparus_II_AUV_SN0001",
    "sensor_id": "SBE16_SN57353_6479",
    "TEMP": temp, "TEMP_QC": 1,
    "CNDC": cndc, "CNDC_QC": 1,
    "PRES": pres, "PRES_QC": 1,
    "PSAL": psal, "PSAL_QC": 1

})
to_csv(df, folder, "AUV_SN0002.csv")
guess_command(folder)



# ============ ASV with an ADCP ============ #
folder = "10"
times = pd.date_range("2024-01-01T00:00:00Z", "2024-03-31T23:59:00Z", freq="30min")
t = np.arange(0, len(times)) / len(times)

array_by_depth = []

for depth in range(10, 101, 10):
    cspd = np.abs(3 * np.sin(2*np.pi*t  +  depth/100*2*np.pi))
    cdir = 180 + 180 * np.sin(2*np.pi*t  +  depth/100*2*np.pi)
    latitude = 41.206253 - 0.3 * t + 0.1 * np.cos(10 * 2 * np.pi * t )
    longitude = 1.824103 + t  # + np.abs(np.sin(10*2*np.pi*t))
    array_by_depth.append((depth, latitude, longitude, cspd, cdir))

dataframes = []
for depth,  latitude, longitude, cspd, cdir in array_by_depth:
    df = pd.DataFrame({
        "time": times,
        "depth": np.zeros(len(t)) + depth,
        "latitude": latitude,
        "longitude": longitude,
        "CSPD": cspd,
        "CDIR": cdir,
        "CSPD_QC": 1,
        "CDIR_QC": 1
    })
    dataframes.append(df)

df = pd.concat(dataframes)

to_csv(df, folder, "ADCP_on_ASV.csv")
guess_command(folder)

