"""Module defining the Autocorrelation fingerprint feature implementation."""

from typing import Sequence, Optional
from multiprocessing import cpu_count
from skfp.fingerprints.autocorr import AutocorrFingerprint
from rdkit.Chem.rdchem import Mol
import numpy as np
from hammer.molecular_features.feature_interface import FeatureInterface


class AutocorrelationFingerprint(FeatureInterface):
    """Class defining the Autocorrelation fingerprint feature implementation."""

    def __init__(self, verbose: bool = True, n_jobs: Optional[int] = None) -> None:
        """Initialize the Autocorrelation fingerprint feature."""
        super().__init__(n_jobs=n_jobs, verbose=verbose)
        if n_jobs is None or n_jobs < 1:
            n_jobs = cpu_count()

        self._fingerprint = AutocorrFingerprint(
            n_jobs=n_jobs,
            verbose={"leave": False, "dynamic_ncols": True, "disable": not verbose},
        )

    def transform_molecules(self, molecules: Sequence[Mol]) -> np.ndarray:
        """Transform a molecule into a feature representation."""
        return self._fingerprint.transform(molecules)

    def name(self) -> str:
        """Get the name of the feature."""
        return "Auto-Correlation"

    @staticmethod
    def pythonic_name() -> str:
        """Get the pythonic name of the feature."""
        return "autocorrelation"

    def size(self) -> int:
        """Get the size of the feature."""
        return 192

    @staticmethod
    def dtype() -> np.dtype:
        """Get the data type of the feature."""
        return np.float32

    @staticmethod
    def is_binary() -> bool:
        """Returns whether the feature is binary."""
        return False

    @staticmethod
    def argparse_description() -> str:
        """Get the argparse description of the feature."""
        return (
            "Autocorrelation fingerprint is descriptor-based fingerprint, "
            "where bits measure strength of autocorrelation of molecular "
            "properties between atoms with different shortest path distances."
        )
