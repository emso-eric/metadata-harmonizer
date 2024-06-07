#!/usr/bin/env python3
"""
Re-implementation of the WaterFrame class. Originally implemented in the mooda package, it is no longer maintained, so
a custom re-implementation is included here.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 6/6/24
"""
import pandas as pd


class WaterFrame:
    def __init__(self, data: pd.DataFrame, metadata: dict, vocabulary: dict):
        """
        This class is a lightweight re-implementation of WaterFrames, originally from mooda package. It has been
        reimplemented due to lack of maintenance of the original package.
        """
        assert type(data) is pd.DataFrame
        assert type(metadata) is dict
        assert type(vocabulary) is dict

        self.data = data  # Here, we should have a dataframe
        self.metadata = metadata
        self.vocabulary = vocabulary

        # Now make sure that all variables have an entry in the vocabulary

        for col in self.data.columns:
            assert col in self.vocabulary.keys(), f"Vocabulary dict does not have netry for {col}"
