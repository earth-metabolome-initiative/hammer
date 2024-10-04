"""Submodule providing the multi-modal multi-class classifier model.

Implementative details
----------------------
The model is a feed-forward neural network based on Keras/TensorFlow.

Multimodality
~~~~~~~~~~~~~~~~~~~~~~
The model receives a dictionary of inputs, where the keys are the name
of the modality and the values are the input tensors.
For each modality, it initializes a separate sub-module. The sub-modules
are responsible for processing the input tensors of the corresponding modality.

Multiclass
~~~~~~~~~~~~~~~~~~~~~~
The model receives three main output tensors, one for each class level
(pathway, superclass, class). Each output tensor is itself a vector of
binary values, where each value corresponds to a class label.
Some samples may have multiple class labels for any given class level,
and as such, the model uses a binary cross-entropy loss function for
each output tensor, with a sigmoid activation function. Each head of
the model is a separate sub-module, responsible for processing the output
tensor of the corresponding class level.
"""

from typing import Dict, Optional, Tuple, List
import os
from tensorflow.keras.models import (  # pylint: disable=no-name-in-module,import-error
    Model,  # pylint: disable=no-name-in-module,import-error
)
from tensorflow.keras.layers import (  # pylint: disable=no-name-in-module,import-error
    Concatenate,  # pylint: disable=no-name-in-module,import-error
    Layer,  # pylint: disable=no-name-in-module,import-error
    Input,  # pylint: disable=no-name-in-module,import-error
    Dense,  # pylint: disable=no-name-in-module,import-error
    BatchNormalization,  # pylint: disable=no-name-in-module,import-error
    Dropout,  # pylint: disable=no-name-in-module,import-error
)
from tensorflow.keras.utils import (  # pylint: disable=no-name-in-module,import-error
    plot_model,  # pylint: disable=no-name-in-module,import-error
)
from tensorflow.keras.callbacks import (  # pylint: disable=no-name-in-module,import-error
    ModelCheckpoint,  # pylint: disable=no-name-in-module,import-error
    TerminateOnNaN,  # pylint: disable=no-name-in-module,import-error
    ReduceLROnPlateau,  # pylint: disable=no-name-in-module,import-error
    EarlyStopping,  # pylint: disable=no-name-in-module,import-error
)
from tensorflow.keras.optimizers import (  # pylint: disable=no-name-in-module,import-error
    Adam,  # pylint: disable=no-name-in-module,import-error
)
from tensorflow.keras.initializers import (  # pylint: disable=no-name-in-module,import-error
    HeNormal,  # pylint: disable=no-name-in-module,import-error
)
from tensorflow.keras.saving import (  # pylint: disable=no-name-in-module,import-error
    load_model,  # pylint: disable=no-name-in-module,import-error
)
from tensorflow.keras.losses import (  # pylint: disable=no-name-in-module,import-error
    SquaredHinge,  # pylint: disable=no-name-in-module,import-error
)
import compress_json
from downloaders import BaseDownloader
from tqdm.keras import TqdmCallback
import numpy as np
import pandas as pd
from plot_keras_history import plot_history
from extra_keras_metrics import get_standard_binary_metrics
from np_classifier.training.molecular_features import compute_features


class Classifier:
    """Class representing the multi-modal multi-class classifier model."""

    def __init__(self):
        """Initialize the classifier model."""
        self._model: Optional[Model] = None
        self._history: Optional[pd.DataFrame] = None
        self._pathway_names: Optional[List[str]] = None
        self._superclass_names: Optional[List[str]] = None
        self._class_names: Optional[List[str]] = None

    @staticmethod
    def load(model_name: str) -> "Classifier":
        """Load a classifier model from a file."""
        all_model_data = compress_json.local_load("models.json")
        model_data: Optional[Dict[str, str]] = None
        for model in all_model_data:
            if model["model_name"] == model_name:
                model_data = model
                break
        if model_data is None:
            available_model_names = [model["model_name"] for model in all_model_data]
            raise ValueError(
                f"Model {model_name} not found. Available models: {available_model_names}"
            )

        # We download the model weights and metadata from Zenodo.
        downloader = BaseDownloader()
        model_path = f"downloads/{model_data['model_name']}.keras"
        class_names_path = f"downloads/{model_data['model_name']}.class_names.json"
        pathway_names_path = f"downloads/{model_data['model_name']}.pathway_names.json"
        superclass_names_path = (
            f"downloads/{model_data['model_name']}.superclass_names.json"
        )
        downloader.download(
            urls=[
                model_data["model_url"],
                model_data["class_names"],
                model_data["pathway_names"],
                model_data["superclass_names"],
            ],
            paths=[
                model_path,
                class_names_path,
                pathway_names_path,
                superclass_names_path,
            ],
        )

        classifier = Classifier()
        classifier._model = load_model(model_path)
        classifier._class_names = compress_json.load(class_names_path)
        classifier._pathway_names = compress_json.load(pathway_names_path)
        classifier._superclass_names = compress_json.load(superclass_names_path)
        return classifier

    def predict_smile(
        self, smile: str, include_top_k: Optional[int] = 10
    ) -> Dict[str, str]:
        """Predict the class labels for a single SMILES string."""
        assert isinstance(smile, str)
        assert len(smile) > 0
        model_input_layer_names = list(self._model.input.keys())
        features: Dict[str, np.ndarray] = compute_features(
            smile,
            include_morgan_fingerprint="morgan_fingerprint" in model_input_layer_names,
            include_rdkit_fingerprint="rdkit_fingerprint" in model_input_layer_names,
            include_atom_pair_fingerprint="atom_pair_fingerprint"
            in model_input_layer_names,
            include_topological_torsion_fingerprint="topological_torsion_fingerprint"
            in model_input_layer_names,
            include_feature_morgan_fingerprint="feature_morgan_fingerprint"
            in model_input_layer_names,
            include_avalon_fingerprint="avalon_fingerprint" in model_input_layer_names,
            include_maccs_fingerprint="maccs_fingerprint" in model_input_layer_names,
            include_map4_fingerprint="map4_fingerprint" in model_input_layer_names,
            include_descriptors="descriptors" in model_input_layer_names,
        )

        features: Dict[str, np.ndarray] = {
            key: value.reshape(1, -1) for key, value in features.items()
        }

        predictions = self._model.predict(features)

        pathway_predictions = dict(zip(self._pathway_names, predictions["pathway"][0]))
        superclass_predictions = dict(
            zip(self._superclass_names, predictions["superclass"][0])
        )
        class_predictions = dict(zip(self._class_names, predictions["class"][0]))

        if include_top_k is not None:
            pathway_predictions = dict(
                sorted(
                    pathway_predictions.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:include_top_k]
            )
            superclass_predictions = dict(
                sorted(
                    superclass_predictions.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:include_top_k]
            )
            class_predictions = dict(
                sorted(
                    class_predictions.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:include_top_k]
            )

        return {
            "pathway": pathway_predictions,
            "superclass": superclass_predictions,
            "class": class_predictions,
        }

    def _build_input_modality(self, input_layer: Input) -> Layer:
        """Build the input modality sub-module."""
        hidden = input_layer

        if input_layer.shape[1] == 2048:
            hidden_sizes = 768
        else:
            hidden_sizes = 128

        for i in range(4):
            hidden = Dense(
                hidden_sizes,
                activation="relu",
                kernel_initializer=HeNormal(),
                name=f"dense_{input_layer.name}_{i}",
            )(hidden)
            hidden = BatchNormalization(
                name=f"batch_normalization_{input_layer.name}_{i}"
            )(hidden)

        hidden = Dropout(0.4)(hidden)
        return hidden

    def _build_hidden_layers(self, inputs: List[Layer]) -> Layer:
        """Build the hidden layers sub-module."""
        hidden = Concatenate(axis=-1)(inputs)
        for i in range(4):
            hidden = Dense(
                2048,
                activation="relu",
                kernel_initializer=HeNormal(),
                name=f"dense_hidden_{i}",
            )(hidden)
            hidden = BatchNormalization(
                name=f"batch_normalization_hidden_{i}",
            )(hidden)
        hidden = Dropout(0.3)(hidden)
        return hidden

    def _build_pathway_head(self, input_layer: Layer, number_of_pathways: int) -> Layer:
        """Build the output head sub-module."""
        return Dense(number_of_pathways, name="pathway", activation="linear")(
            input_layer
        )

    def _build_superclass_head(
        self, input_layer: Layer, number_of_superclasses: int
    ) -> Layer:
        """Build the output head sub-module."""
        return Dense(number_of_superclasses, name="superclass", activation="linear")(
            input_layer
        )

    def _build_class_head(self, input_layer: Layer, number_of_classes: int) -> Layer:
        """Build the output head sub-module."""
        return Dense(number_of_classes, name="class", activation="linear")(input_layer)

    def _build(
        self,
        inputs: Dict[str, np.ndarray],
        outputs: Dict[str, np.ndarray],
    ):
        """Build the classifier model."""
        # Validate the input types.
        assert isinstance(inputs, dict)
        assert isinstance(outputs, dict)
        assert all(isinstance(value, np.ndarray) for value in inputs.values())
        assert all(isinstance(value, np.ndarray) for value in outputs.values())

        input_layers: List[Input] = [
            Input(shape=input_array.shape[1:], name=name, dtype=input_array.dtype)
            for name, input_array in inputs.items()
        ]

        input_modalities: List[Layer] = [
            self._build_input_modality(input_layer) for input_layer in input_layers
        ]

        hidden: Layer = self._build_hidden_layers(input_modalities)

        pathway_head = self._build_pathway_head(hidden, outputs["pathway"].shape[1])
        superclass_head = self._build_superclass_head(
            hidden, outputs["superclass"].shape[1]
        )
        class_head = self._build_class_head(hidden, outputs["class"].shape[1])

        self._model = Model(
            inputs={input_layer.name: input_layer for input_layer in input_layers},
            outputs={
                "pathway": pathway_head,
                "superclass": superclass_head,
                "class": class_head,
            },
            name="classifier",
        )

    def train(
        self,
        train: Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]],
        val: Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]],
        holdout_number: Optional[int] = None,
        number_of_epochs: int = 10_000,
    ):
        """Train the classifier model."""
        self._build(*train)
        # We setup loss weights so that the output with more classes, which is the harder
        # to predict, has a higher weight.
        total_number_of_outputs = sum((
            output.shape[1]
            for output in train[1].values()
        ))
        loss_weights = {
            "pathway": train[1]["pathway"].shape[1] / total_number_of_outputs,
            "superclass": train[1]["superclass"].shape[1] / total_number_of_outputs,
            "class": train[1]["class"].shape[1] / total_number_of_outputs,
        }
        self._model.compile(
            optimizer=Adam(),
            loss=SquaredHinge(),
            metrics={
                "pathway": get_standard_binary_metrics(),
                "superclass": get_standard_binary_metrics(),
                "class": get_standard_binary_metrics(),
            },
            loss_weights=loss_weights,
        )
        plot_model(
            self._model,
            to_file="model.png",
            show_shapes=True,
            show_dtype=True,
            show_layer_names=True,
            expand_nested=True,
            dpi=100,
            show_layer_activations=True,
            show_trainable=True,
        )

        if holdout_number is not None:
            model_checkpoint_path = f"model_checkpoint_{holdout_number}.keras"
        else:
            model_checkpoint_path = "model_checkpoint.keras"

        model_checkpoint = ModelCheckpoint(
            model_checkpoint_path,
            monitor="val_class_mcc",
            save_best_only=True,
            save_weights_only=False,
            mode="auto",
            save_freq="epoch",
            verbose=0,
        )

        learning_rate_scheduler = ReduceLROnPlateau(
            monitor="val_class_mcc",  # Monitor the validation loss to avoid overfitting.
            factor=0.8,  # Reduce the learning rate by a small factor (e.g., 20%) to prevent abrupt drops.
            patience=100,  # Wait for 20 epochs without improvement before reducing LR (long patience to allow grokking).
            verbose=1,  # Verbose output for logging learning rate reductions.
            mode="max",  # Minimize the validation loss.
            min_delta=1e-4,  # Small change threshold for improvement, encouraging gradual learning.
            cooldown=150,  # After a learning rate reduction, wait 10 epochs before resuming normal operation.
            min_lr=1e-6,  # Set a minimum learning rate to avoid reducing it too much and stalling learning.
        )

        early_stopping = EarlyStopping(
            monitor="val_class_mcc",
            patience=500,
            verbose=1,
            mode="max",
            restore_best_weights=True,
        )

        # We compute the sample weights by combining the reciprocal of the class frequencies.
        # We start by counting the number of samples for each class.
        pathway_counts = train[1]["pathway"].sum(axis=0)
        superclass_counts = train[1]["superclass"].sum(axis=0)
        class_counts = train[1]["class"].sum(axis=0)

        # We determine a sample of rarity for each sample. When a sample has multiple classes,
        # we determine its rarity by multiplying the rarity of each class.
        number_of_samples = train[1]["pathway"].shape[0]

        pathway_sample_rarity = np.fromiter(
            (
                np.sum(number_of_samples / pathway_counts[sample_pathways == 1])
                for sample_pathways in train[1]["pathway"]
            ),
            dtype=np.float32,
        )
        superclass_sample_rarity = np.fromiter(
            (
                np.sum(number_of_samples / superclass_counts[sample_superclasses == 1])
                for sample_superclasses in train[1]["superclass"]
            ),
            dtype=np.float32,
        )
        class_sample_rarity = np.fromiter(
            (
                np.sum(number_of_samples / class_counts[sample_classes == 1])
                for sample_classes in train[1]["class"]
            ),
            dtype=np.float32,
        )

        sample_weight = {
            "pathway": pathway_sample_rarity,
            "superclass": superclass_sample_rarity,
            "class": class_sample_rarity,
        }

        training_history = self._model.fit(
            *train,
            epochs=number_of_epochs,
            callbacks=[
                TqdmCallback(
                    verbose=1,
                    metrics=[
                        "loss",
                        "val_loss",
                        "class_mcc",
                        "val_class_mcc",
                        "superclass_mcc",
                        "val_superclass_mcc",
                        "pathway_mcc",
                        "val_pathway_mcc",
                    ],
                ),
                model_checkpoint,
                TerminateOnNaN(),
                early_stopping,
                learning_rate_scheduler,
            ],
            sample_weight=sample_weight,
            batch_size=4096,
            shuffle=True,
            verbose=0,
            validation_data=val,
        )
        self._history = pd.DataFrame(training_history.history)

        fig, _ = plot_history(
            self._history, monitor="val_class_mcc", monitor_mode="max"
        )

        # We create a directory 'histories' if it does not exist.
        os.makedirs("histories", exist_ok=True)

        if holdout_number is not None:
            self._history.to_csv(f"histories/history_{holdout_number}.csv")
            fig.savefig(f"histories/history_{holdout_number}.png")
        else:
            self._history.to_csv("histories/history.csv")
            fig.savefig("histories/history.png")

    def evaluate(
        self, test: Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]
    ) -> Dict[str, float]:
        """Evaluate the classifier model."""
        return self._model.evaluate(*test, verbose=0, return_dict=True)
