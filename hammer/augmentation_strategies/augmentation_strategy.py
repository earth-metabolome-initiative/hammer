"""Submodule providing strategies to extend the smiles in the training dataset."""

from typing import List, Optional
from multiprocessing import Pool
from abc import ABC, abstractmethod
from tqdm.auto import tqdm
from rdkit.RDLogger import EnableLog, DisableLog  # type: ignore


class AugmentationStrategy(ABC):
    """Base class for augmentation strategies."""

    def __init__(
        self, maximal_number: int, n_jobs: Optional[int] = 1, verbose: bool = True
    ):
        """Initialize the augmentation strategy."""
        self._maximal_number = maximal_number
        self._n_jobs = n_jobs
        self._verbose = verbose

    @abstractmethod
    def name(self) -> str:
        """Return the name of the augmentation strategy."""
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def pythonic_name() -> str:
        """Return the pythonic name of the augmentation strategy."""
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def argparse_description() -> str:
        """Return the argparse description of the augmentation strategy."""
        raise NotImplementedError

    @abstractmethod
    def augment(self, smiles: str) -> List[str]:
        """Augment a smiles."""
        raise NotImplementedError

    def augment_all(self, smiles: List[str]) -> List[List[str]]:
        """Augment a list of smiles."""
        DisableLog("rdApp.*")  # pylint: disable=no-member
        with Pool(self._n_jobs) as pool:
            results = list(
                tqdm(
                    pool.imap(self.augment, smiles),
                    total=len(smiles),
                    disable=not self._verbose,
                    desc=self.name(),
                    dynamic_ncols=True,
                    leave=False,
                )
            )
            pool.close()
            pool.join()

        EnableLog("rdApp.*")  # pylint: disable=no-member

        return results
