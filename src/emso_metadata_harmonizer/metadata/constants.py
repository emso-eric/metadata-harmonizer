#!/usr/bin/env python3
import numpy as np

dimensions = ["time", "depth"]
iso_time_format = "%Y-%m-%dT%H:%M:%SZ"
qc_flags = {
    "unknown": 0,
    "good_data": 1,
    "probably_good_data": 2,
    "potentially_correctable_bad_data": 3,
    "bad_data": 4,
    "nominal_value": 7,
    "interpolated_value": 8,
    "missing_value": 9
}

fill_value = -999999  # default, for floats
fill_value_uint8 = 254

def null_by_dtype(dtype):
    if dtype in [float, np.float32, np.float64, np.float128]:
        return np.nan
    elif dtype in [np.int32, np.int64]:
        return -9999
    elif dtype is np.uint8:
        return 255
    elif dtype is str:
        return ""
    else:
        raise ValueError(f"Dtype {dtype} not supported!")
