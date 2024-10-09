"""Submodule providing utilities for parsing command line arguments."""

from hammer.executables.argument_parser_utilities.augmentation_arguments import (
    add_augmentation_settings_arguments,
    build_augmentation_settings_from_namespace,
)
from hammer.executables.argument_parser_utilities.features_arguments import (
    add_features_arguments,
    build_features_settings_from_namespace,
)
from hammer.executables.argument_parser_utilities.shared_arguments import (
    add_shared_arguments,
)

__all__ = [
    "add_augmentation_settings_arguments",
    "build_augmentation_settings_from_namespace",
    "add_features_arguments",
    "build_features_settings_from_namespace",
    "add_shared_arguments",
]