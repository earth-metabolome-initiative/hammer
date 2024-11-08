"""MACCS fingerprint feature implementation using scikit-fingerprints."""

from typing import Sequence, Optional
from multiprocessing import cpu_count
from skfp.fingerprints.maccs import MACCSFingerprint as MACCSFingerprintSKFP
from rdkit.Chem.rdchem import Mol
import numpy as np
from hammer.molecular_features.feature_interface import BinaryFeatureInterface


class MACCSFingerprint(BinaryFeatureInterface):
    """Class defining the MACCS fingerprint feature implementation."""

    def __init__(self, verbose: bool = True, n_jobs: Optional[int] = None) -> None:
        """Initialize the MACCS fingerprint feature."""
        super().__init__(n_jobs=n_jobs, verbose=verbose)
        if n_jobs is None or n_jobs < 1:
            n_jobs = cpu_count()

        self._fingerprint = MACCSFingerprintSKFP(
            n_jobs=n_jobs,
            verbose={"leave": False, "dynamic_ncols": True, "disable": not verbose},
        )

    def transform_molecules(self, molecules: Sequence[Mol]) -> np.ndarray:
        """Transform a molecule into a feature representation."""
        return self._fingerprint.transform(molecules)

    def name(self) -> str:
        """Get the name of the feature."""
        return "MACCS"

    @staticmethod
    def pythonic_name() -> str:
        """Get the pythonic name of the feature."""
        return "maccs"

    def size(self) -> int:
        """Get the size of the feature."""
        # Features equal to 166
        return self._fingerprint.n_features_out

    @staticmethod
    def argparse_description() -> str:
        """Get the argparse description of the feature."""
        return (
            "This is a substructure fingerprint, based "
            "on publicly available MDL definitions, and "
            "refined by Gregory Landrum for RDKit."
        )
