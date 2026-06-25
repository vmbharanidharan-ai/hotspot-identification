"""pmhc-hotspot: structure-aware hotspot selection for peptide-MHC complexes."""

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.types import HotspotPatch, PredictionResult, ResidueScore

__version__ = "0.3.0"
__all__ = [
    "HotspotPatch",
    "HotspotPredictor",
    "PredictionResult",
    "ResidueScore",
    "__version__",
]
