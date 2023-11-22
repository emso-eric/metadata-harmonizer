#!/usr/bin/env python3
import pandas as pd
import numpy as np
import rich

times = pd.date_range("2023-01-01T00:00:00z", "2023-01-02T00:00:00z", freq="30min")
N = len(times)
rich.print(times)

t = 2*np.arange(0, N) / N
rich.print(f"{len(t)} {N}")

temp = 10 + 5*np.sin(2*np.pi*t)
cndc = 5 + 0.5*np.sin(2*np.pi*t)
depth = 10 + 0.5*np.sin(2*np.pi*t)

df = pd.DataFrame({"TIME": times, "TEMP":  temp, "CNDC": cndc, "DEPTH": depth})
df.to_csv("dummyData.csv", index=False, float_format="%.03f")
