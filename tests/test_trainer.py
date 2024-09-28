"""Submodule to test complete execution of the training pipeline."""

import silence_tensorflow.auto  # pylint: disable=unused-import
from np_classifier.training import Trainer, SmilesDataset


def test_train():
    """Train the model."""
    dataset = SmilesDataset(number_of_splits=2)
    trainer = Trainer(dataset, number_of_epochs=3)
    _holdout_performance = trainer.holdouts()
