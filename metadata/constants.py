#!/usr/bin/env python3

dimensions = ["time", "latitude", "longitude", "depth", "sensor_id"]
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

fill_value = -999999