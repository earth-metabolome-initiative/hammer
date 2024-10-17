"""Extended Connectivity fingerprint feature implementation."""

from typing import Sequence, Optional
from multiprocessing import cpu_count
from skfp.fingerprints.ecfp import ECFPFingerprint
from skfp.utils import TQDMSettings
from rdkit.Chem.rdchem import Mol
import numpy as np
from hammer.features.feature_interface import BinaryFeatureInterface


class ExtendedConnectivityFingerprint(BinaryFeatureInterface):
    """Class defining the Extended Connectivity fingerprint feature implementation."""

    def __init__(
        self,
        fp_size: int = 2048,
        radius: int = 2,
        verbose: bool = True,
        n_jobs: Optional[int] = None,
    ) -> None:
        """Initialize the Extended Connectivity fingerprint feature."""
        if n_jobs is None or n_jobs < 1:
            n_jobs = cpu_count()
        self._fp_size = fp_size
        self._radius = radius
        tqdm_settings = (
            TQDMSettings().leave(False).desc(self.name()).dynamic_ncols(True)
        )
        if not verbose:
            tqdm_settings = tqdm_settings.disable()
        self._fingerprint = ECFPFingerprint(
            fp_size=fp_size, radius=radius, n_jobs=n_jobs, verbose=tqdm_settings
        )

    def transform_molecules(self, molecules: Sequence[Mol]) -> np.ndarray:
        """Transform a molecule into a feature representation."""
        return self._fingerprint.transform(molecules)

    def name(self) -> str:
        """Get the name of the feature."""
        return f"Extended Connectivity ({self._radius}r, {self._fp_size}b)"

    @staticmethod
    def pythonic_name() -> str:
        """Get the pythonic name of the feature."""
        return "extended_connectivity"

    def size(self) -> int:
        """Get the size of the feature."""
        return self._fp_size

    @staticmethod
    def low_cardinality() -> bool:
        """Return whether the feature has low cardinality."""
        return False

    @staticmethod
    def argparse_description() -> str:
        """Get the argparse description of the feature."""
        return (
            "Extended Connectivity fingerprint where fragments "
            "are computed based on circular substructures around each atom."
        )