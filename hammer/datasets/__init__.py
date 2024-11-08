"""Submodule providing Dataset classes for the Hammer model."""

from typing import List, Type
from hammer.datasets.dataset import Dataset
from hammer.datasets.npc import NPCDataset, NPCScrapedDataset, NPCHarmonizedDataset
from hammer.datasets.gnps import GNPSDataset

AVAILABLE_DATASETS: List[Type[Dataset]] = [
    NPCDataset,
    NPCScrapedDataset,
    NPCHarmonizedDataset,
    GNPSDataset,
]

__all__ = [
    "Dataset",
    "NPCDataset",
    "NPCScrapedDataset",
    "NPCHarmonizedDataset",
    "GNPSDataset",
    "AVAILABLE_DATASETS",
]
