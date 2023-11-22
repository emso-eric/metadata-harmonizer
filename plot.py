#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 16/5/23
"""

from metadata.netcdf import new_read_nc2
wf = new_read_nc2("2ctds_2021.nc")
df = wf.data
print(df)

df16 = df[df["SENSOR_ID"] == "16P57353-6479"]
print(df16)

df37 = df[df["SENSOR_ID"] == "37SMP47472-5496"]
print(df37)


df_random = df[df["PSAL"] == 38.0413]
print(df_random)