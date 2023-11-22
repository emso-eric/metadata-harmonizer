#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 23/3/23
"""
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import rich

tests = pd.read_csv("data.csv")

institutions = tests["institution"].unique()
rich.print(institutions)
alltests = tests.copy()

d = {
    "institution": [],
    "ndatasets": [],
    "tests_passed": [],
    "required_passed": [],
    "optional_passed": []
}

for ins in institutions:
    tests = alltests[alltests["institution"] == ins]


    sns.set(style="whitegrid")

    fig, axd = plt.subplot_mosaic([['left', 'right'], ['bottom', 'bottom']],constrained_layout=True, figsize=(14, 8))

    ax2 = axd['left']
    ax3 = axd['right']
    ax1 = axd['bottom']

    ax1.set_title("Total tests")
    ax2.set_title("Required tests")
    ax3.set_title("Optional tests")

    bindwitdh = 5
    sns.histplot(data=tests, x="total", ax=ax1, binwidth=bindwitdh)
    sns.histplot(data=tests, x="required", ax=ax2, binwidth=bindwitdh)
    sns.histplot(data=tests, x="optional", ax=ax3, binwidth=bindwitdh)
    ax1.set_xlim([0, 100])
    ax2.set_xlim([0, 100])
    ax3.set_xlim([0, 100])

    [ax.set_xlabel("tests passed (%)") for ax in [ax1, ax2, ax3]]
    [ax.set_ylabel("number of tests") for ax in [ax1, ax2, ax3]]

    import numpy as np

    fig.suptitle(ins + f" ({len(tests)} datasets)", fontsize=14)

    print(f"total median: {tests['total'].mean()}")
    print(f"required median: {tests['required'].median()}")

    d["institution"].append(ins)
    d["ndatasets"].append(len(tests))
    d["tests_passed"].append(tests['total'].mean())
    d["required_passed"].append(tests['required'].mean())
    d["optional_passed"].append(tests['optional'].mean())

d = pd.DataFrame(d)
d.to_csv("processed_data.csv", float_format="%.2f", index=False)
plt.show()