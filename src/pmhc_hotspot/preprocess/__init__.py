"""Structure ingestion and canonical example building."""

from pmhc_hotspot.preprocess.build_examples import (
    build_dataset,
    build_example_from_entry,
    write_example,
)
from pmhc_hotspot.preprocess.config import DatasetBuildConfig

__all__ = [
    "DatasetBuildConfig",
    "build_dataset",
    "build_example_from_entry",
    "write_example",
]
