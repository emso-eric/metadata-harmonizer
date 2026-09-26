import logging

from .erddap_config import erddap_config
from .erddap import ERDDAP
from .metadata.waterframe import WaterFrame
from .report import metadata_report
from .dataset_generator import generate_dataset
from .metadata.waterframe import WaterFrame
from .metadata import setup_log

logging.getLogger("emso_metadata_harmonizer").addHandler(logging.NullHandler())

__version__ = "1.1.0dev2"