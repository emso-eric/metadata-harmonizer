#!/usr/bin/env python3
"""
File containing Quality Control tools and info following the SeaDataNet recommendations

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 18/4/23
"""

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