"""Structure ingestion and canonical example building."""

from pmhc_hotspot.preprocess.build_examples import (
    build_dataset,
    build_example_from_entry,
    write_example,
)
from pmhc_hotspot.preprocess.config import DatasetBuildConfig
from pmhc_hotspot.preprocess.enrich_features import FeatureEnrichReport, enrich_examples

__all__ = [
    "DatasetBuildConfig",
    "FeatureEnrichReport",
    "build_dataset",
    "build_example_from_entry",
    "enrich_examples",
    "write_example",
]
