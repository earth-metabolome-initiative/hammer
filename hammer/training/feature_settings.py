"""Submodule providing a class defining the features configuration."""

from typing import Dict, Type, Iterator, List
import compress_json
from hammer.training.features import (
    FeatureInterface,
    AutocorrelationFingerprint,
    ExtendedConnectivityFingerprint,
    FunctionalGroupsFingerprint,
    GhoseCrippenFingerprint,
    LaggnerFingerprint,
    LayeredFingerprint,
    LingoFingerprint,
    MinHashedAtomPairFingerprint,
    MinHashedFingerprint,
    MolecularQuantumNumbersFingerprint,
    PatternFingerprint,
    PubChemFingerprint,
    SMILESExtendedConnectivity,
    VanDerWaalsSurfaceAreaFingerprint,
    AvalonFingerprint,
    MACCSFingerprint,
    AtomPairFingerprint,
    TopologicalTorsionFingerprint,
    RDKitFingerprint,
)

FEATURES: List[Type[FeatureInterface]] = [
    AutocorrelationFingerprint,
    AtomPairFingerprint,
    ExtendedConnectivityFingerprint,
    FunctionalGroupsFingerprint,
    GhoseCrippenFingerprint,
    LaggnerFingerprint,
    LayeredFingerprint,
    LingoFingerprint,
    MinHashedAtomPairFingerprint,
    MinHashedFingerprint,
    MolecularQuantumNumbersFingerprint,
    PatternFingerprint,
    PubChemFingerprint,
    SMILESExtendedConnectivity,
    VanDerWaalsSurfaceAreaFingerprint,
    AvalonFingerprint,
    MACCSFingerprint,
    TopologicalTorsionFingerprint,
    RDKitFingerprint,
]


class FeatureSettings:
    """Class defining the features configuration."""

    def __init__(self):
        """Initialize the feature settings."""
        self._features_included: Dict[str, bool] = {}

        for feature in FEATURES:
            # We initialize all features as not included
            self._features_included[feature.pythonic_name()] = False

    def __getattr__(self, name):
        # If the attribute name starts with 'include_', handle it dynamically
        if name.startswith("include_"):
            feature_name = name[len("include_") :]
            if feature_name in self._features_included:
                return lambda: self._include_feature(feature_name)
        raise AttributeError(
            f"{self.__class__.__name__} object has no attribute '{name}'"
        )

    @staticmethod
    def from_dict(features: Dict[str, bool]) -> "FeatureSettings":
        """Create feature settings from a dictionary."""
        feature_settings = FeatureSettings()
        for feature_name, included in features.items():
            if included:
                getattr(feature_settings, f"include_{feature_name}")()
        return feature_settings

    @staticmethod
    def from_json(path: str) -> "FeatureSettings":
        """Create feature settings from a JSON string."""
        return FeatureSettings.from_dict(compress_json.load(path))

    @staticmethod
    def from_feature_class(feature_class: Type[FeatureInterface]) -> "FeatureSettings":
        """Create feature settings from a feature class."""
        feature_settings = FeatureSettings()
        getattr(feature_settings, f"include_{feature_class.pythonic_name()}")()
        return feature_settings

    def to_dict(self) -> Dict[str, bool]:
        """Convert the settings to a dictionary."""
        return self._features_included

    @staticmethod
    def standard() -> "FeatureSettings":
        """Get the standard feature settings."""
        return (
            FeatureSettings()
            .include_layered()
            .include_molecular_descriptors()
            .include_maccs()
        )

    def include_all(self) -> "FeatureSettings":
        """Include all features."""
        for key in self._features_included:
            self._features_included[key] = True
        return self

    def include_all_low_cardinality(self) -> "FeatureSettings":
        """Include all low cardinality features."""
        for feature in FEATURES:
            if feature.low_cardinality():
                self._features_included[feature.pythonic_name()] = True
        return self

    def includes_features(self) -> bool:
        """Check if any features are included."""
        return any(self._features_included.values())

    def number_of_features(self) -> int:
        """Get the number of features."""
        return sum(self._features_included.values())

    def _include_feature(self, feature_name: str) -> "FeatureSettings":
        """Set the value of a feature."""
        self._features_included[feature_name] = True
        return self

    def iter_features(self) -> Iterator[Type[FeatureInterface]]:
        """Iterate over the features."""
        for feature in FEATURES:
            if self._features_included[feature.pythonic_name()]:
                yield feature