"""Module containing the hierarchical multi-modal multi-class classifier model."""

from typing import Dict, Optional, Any, List, Union
import os
import shutil
from copy import deepcopy
import warnings
from keras import Model  # type: ignore
from keras.api.layers import (  # type: ignore
    Concatenate,
    Input,
    Dense,
    Dropout,
    Conv1D,
    Flatten,
    MaxPool1D,
    GlobalAveragePooling1D,
    BatchNormalization,
    Masking,
)
from keras.api.losses import BinaryFocalCrossentropy  # type: ignore
from keras.api.utils import plot_model  # type: ignore
from keras.api.callbacks import (  # type: ignore
    TerminateOnNaN,
    ReduceLROnPlateau,
    EarlyStopping,
    History,
)
from keras.api.optimizers import (  # type: ignore
    Adam,
)
from keras.api.initializers import GlorotNormal, HeNormal  # type: ignore
from keras.api.saving import (  # type: ignore
    load_model,
)
from keras.api import KerasTensor  # type: ignore
import compress_json
from downloaders import BaseDownloader
from tqdm.keras import TqdmCallback
from tqdm.auto import tqdm
import numpy as np
import pandas as pd
from matchms import Spectrum
import compress_pickle  # type: ignore
from sklearn.preprocessing import RobustScaler  # type: ignore
from extra_keras_metrics import (
    get_complete_binary_metrics,
    get_minimal_multiclass_metrics,
)
from hammer.feature_settings import FeatureSettings
from hammer.augmentation_settings import AugmentationSettings
from hammer.utils import into_canonical_smiles, smiles_to_molecules
from hammer.dags import LayeredDAG
from hammer.initializers import LogitBiasInitializer
from hammer.layers import (
    HarmonizeGraphConvolution,
    TransformerEncoder,
    SinePositionEncoding,
)
from hammer.scalers import (
    SpectralMetadataExtractor,
    SpectralTransformerPreprocessing,
    SpectraScaler,
)


class Hammer:
    """Hierarchical Augmented Multi-modal Multi-class classifiER."""

    def __init__(
        self,
        dag: LayeredDAG,
        feature_settings: FeatureSettings,
        scalers: Dict[str, RobustScaler],
        spectral_preprocessor: Optional[SpectralTransformerPreprocessing] = None,
        spectral_scaler: Optional[SpectraScaler] = None,
        spectral_metadata_extractor: Optional[SpectralMetadataExtractor] = None,
        metadata: Optional[Dict[str, Any]] = None,
        model_path: Optional[str] = None,
        verbose: bool = False,
        n_jobs: Optional[int] = None,
    ):
        """Initialize the classifier model.

        Parameters
        ----------
        label_names : Dict[str, List[str]]
            Dictionary of label names, with the keys being the label categories.
        dag : Dict[str, Dict[str, List[str]]]
            Directed acyclic graph defining the relationships between the labels.
        feature_settings : FeatureSettings
            Feature settings used to compute the features.
        scalers : Optional[Dict[str, RobustScaler]]
            Dictionary of scalers used to scale the features.
        spectral_preprocessor : Optional[SpectralTransformerPreprocessing]
            Scaler used to scale the spectral data.
        spectral_scaler : Optional[SpectraScaler]
            Preprocessor used to preprocess the spectral data.
        spectral_metadata_extractor : Optional[SpectralMetadataExtractor]
            Extractor used to extract metadata from the spectral data.
        metadata : Optional[Dict[str, Any]]
            Metadata of the classifier model.
            Used to store additional information about the classifier.
        model_path : Optional[str]
            Path to the classifier model, if it has been trained.
        verbose : bool
            Whether to display a progress bar.
        n_jobs : Optional[int]
            The number of jobs to use for parallel processing.
        """
        # Some healthy defensive programming.
        assert scalers is None or isinstance(scalers, dict)

        if model_path is not None:
            self._model: Optional[Model] = load_model(model_path)
        else:
            self._model = None

        self._scalers: Dict[str, RobustScaler] = scalers
        self._spectral_preprocessor: Optional[SpectralTransformerPreprocessing] = (
            spectral_preprocessor
        )
        self._spectral_scaler: Optional[SpectraScaler] = spectral_scaler
        self._spectral_metadata_extractor: Optional[SpectralMetadataExtractor] = (
            spectral_metadata_extractor
        )
        self._dag: LayeredDAG = dag
        self._feature_settings: FeatureSettings = feature_settings
        self._verbose: bool = verbose
        self._n_jobs: Optional[int] = n_jobs
        self._metadata: Optional[Dict[str, Any]] = metadata

    @property
    def layered_dag(self) -> LayeredDAG:
        """Return the directed acyclic graph of the classifier model."""
        return self._dag

    @classmethod
    def load_from_path(cls, path: str) -> "Hammer":
        """Load a classifier model from a file."""

        if path.endswith(".tar.gz"):
            # We extract the files from the tar.gz file.
            os.system(f"tar -xzf {path}")

            path = path[:-7]

        dag_path = f"{path}/dag.pkl"
        scalers_path = f"{path}/scalers.pkl"
        spectral_preprocessor_path = f"{path}/spectral_preprocessor.pkl"
        spectral_scaler_path = f"{path}/spectral_scaler.pkl"
        spectral_metadata_extractor_path = f"{path}/spectral_metadata_extractor.pkl"
        model_path = f"{path}/model.keras"
        feature_settings_path = f"{path}/feature_settings.json"

        classifier = Hammer(
            dag=compress_pickle.load(dag_path),
            scalers=compress_pickle.load(scalers_path),
            spectral_preprocessor=(
                compress_pickle.load(spectral_preprocessor_path)
                if os.path.exists(spectral_preprocessor_path)
                else None
            ),
            spectral_scaler=(
                compress_pickle.load(spectral_scaler_path)
                if os.path.exists(spectral_scaler_path)
                else None
            ),
            spectral_metadata_extractor=(
                compress_pickle.load(spectral_metadata_extractor_path)
                if os.path.exists(spectral_metadata_extractor_path)
                else None
            ),
            feature_settings=FeatureSettings.from_json(feature_settings_path),
            model_path=model_path,
        )

        return classifier

    @classmethod
    def load(cls, version: str) -> "Hammer":
        """Load a classifier model from a file."""
        all_models: List[Dict[str, str]] = compress_json.local_load("models.json")
        model_metadata: Optional[Dict[str, str]] = None
        for model in all_models:
            if model["version"] == version:
                model_metadata = model
                break

        if model_metadata is None:
            available_versions = [model["version"] for model in all_models]
            raise ValueError(
                f"Version {version} not found. Available versions: {available_versions}."
            )

        # We download the model weights and metadata from Zenodo.
        downloader = BaseDownloader()
        path = f"downloads/{version}.tar.gz"
        downloader.download(urls=model_metadata["url"], paths=path)

        return Hammer.load_from_path(os.path.join("downloads", version, version))

    def _build_input_modality(self, input_layer: Input) -> KerasTensor:
        """Build the input modality b-module."""
        hidden = input_layer
        if len(input_layer.shape) == 3:
            while hidden.shape[1] > 256:
                hidden = Conv1D(
                    128,
                    5,
                    activation="relu",
                    kernel_initializer=GlorotNormal(),
                    padding="same",
                )(hidden)
                hidden = BatchNormalization()(hidden)
                hidden = MaxPool1D()(hidden)
                hidden = Dropout(0.2)(hidden)
            positional_encoding = SinePositionEncoding()(hidden)
            hidden = hidden + positional_encoding
            for _ in range(3):
                hidden = TransformerEncoder(
                    intermediate_dim=512,
                    num_heads=2,
                    dropout_rate=0.2,
                    activation="relu",
                    kernel_initializer=HeNormal(),
                )(hidden)
            hidden = GlobalAveragePooling1D()(hidden)
        elif len(input_layer.shape) == 2:
            if input_layer.shape[1] > 768:
                hidden_sizes = 768
            elif input_layer.shape[1] > 512:
                hidden_sizes = 512
            elif input_layer.shape[1] > 256:
                hidden_sizes = 256
            elif input_layer.shape[1] > 128:
                hidden_sizes = 128
            elif input_layer.shape[1] > 64:
                hidden_sizes = 64
            elif input_layer.shape[1] > 32:
                hidden_sizes = 32
            else:
                hidden_sizes = 16
            for i in range(4):
                hidden = Dense(
                    hidden_sizes,
                    activation="relu",
                    kernel_initializer=GlorotNormal(),
                    name=f"dense_{input_layer.name}_{i}",
                )(hidden)
                hidden = BatchNormalization()(hidden)
                if hidden.shape[1] > 16:
                    hidden = Dropout(0.2)(hidden)
        else:
            raise ValueError(f"Input layer has an invalid shape {input_layer.shape}.")
        return hidden

    def _build_hidden_layers(self, inputs: List[KerasTensor]) -> KerasTensor:
        """Build the hidden layers sub-module."""
        if len(inputs) > 1:
            hidden = Concatenate(axis=-1)(inputs)
        else:
            hidden = inputs[0]

        for i in range(2):
            hidden = Dense(
                2048,
                activation="relu",
                kernel_initializer=GlorotNormal(),
                name=f"dense_hidden_{i}",
            )(hidden)
            hidden = BatchNormalization()(hidden)
            hidden = Dropout(0.3)(hidden)
        return hidden

    def _smiles_to_features(self, smiles: List[str]) -> Dict[str, np.ndarray]:
        """Transform a list of SMILES into a dictionary of features."""
        # First, we transform the SMILES to molecules.
        molecules = smiles_to_molecules(
            smiles, verbose=self._verbose, n_jobs=self._n_jobs
        )

        return {
            feature_class.pythonic_name(): feature_class(
                verbose=self._verbose, n_jobs=self._n_jobs
            ).transform_molecules(molecules)
            for feature_class in tqdm(
                self._feature_settings.iter_features(),
                desc="Computing features",
                total=self._feature_settings.number_of_features(),
                disable=not self._verbose,
                dynamic_ncols=True,
                leave=False,
            )
        }

    def fit(
        self,
        train_samples: Union[List[str], List[Spectrum]],
        train_labels: np.ndarray,
        validation_samples: Union[List[str], List[Spectrum]],
        validation_labels: np.ndarray,
        augmentation_settings: Optional[AugmentationSettings] = None,
        model_checkpoint_path: str = "checkpoints/model_checkpoint.keras",
        maximal_number_of_epochs: int = 10_000,
        batch_size: int = 2**9,
    ) -> History:
        """Train the classifier model."""
        spectral_model: bool = isinstance(train_samples[0], Spectrum)

        if spectral_model and self._feature_settings.number_of_features() > 0:
            raise NotImplementedError(
                "Cannot use spectral data and feature settings at the same time."
            )

        if self._metadata is None:
            self._metadata = {}

        self._metadata["feature_settings"] = self._feature_settings.to_dict()
        self._metadata["batch_size"] = batch_size
        self._metadata["spectral_model"] = spectral_model
        self._metadata["maximal_number_of_epochs"] = maximal_number_of_epochs

        if spectral_model:
            self._spectral_preprocessor = SpectralTransformerPreprocessing(
                number_of_peaks=128,
                verbose=self._verbose,
                n_jobs=self._n_jobs,
            )
            self._spectral_scaler = SpectraScaler(
                include_losses=False,
                verbose=self._verbose,
                n_jobs=self._n_jobs,
            )
            self._spectral_metadata_extractor = SpectralMetadataExtractor(
                verbose=self._verbose,
                n_jobs=self._n_jobs,
            )

            self._spectral_preprocessor.fit(train_samples)
            self._spectral_scaler.fit(train_samples)
            self._spectral_metadata_extractor.fit(train_samples)

            train_features: Dict[str, np.ndarray] = {
                "spectra": self._spectral_preprocessor.transform(train_samples),
                "spectra_binned": self._spectral_scaler.transform(train_samples),
                **self._spectral_metadata_extractor.transform(
                    train_samples,
                ),
            }
            validation_features: Dict[str, np.ndarray] = {
                "spectra": self._spectral_preprocessor.transform(validation_samples),
                "spectra_binned": self._spectral_scaler.transform(validation_samples),
                **self._spectral_metadata_extractor.transform(
                    validation_samples,
                ),
            }
        else:
            train_samples = into_canonical_smiles(
                train_samples, verbose=self._verbose, n_jobs=self._n_jobs
            )
            validation_samples = into_canonical_smiles(
                validation_samples, verbose=self._verbose, n_jobs=self._n_jobs
            )

            if augmentation_settings is not None:
                (train_samples, train_labels) = augmentation_settings.augment(
                    train_samples,
                    train_labels,
                    n_jobs=self._n_jobs,
                    verbose=self._verbose,
                )
                self._metadata["augmentation_settings"] = (
                    augmentation_settings.to_dict()
                )
            else:
                self._metadata["augmentation_settings"] = None

            train_features = self._smiles_to_features(train_samples)
            validation_features = self._smiles_to_features(validation_samples)

            # We create a scaler for each feature that is not binary.
            self._scalers = {}
            for feature_class in self._feature_settings.iter_features():
                if not feature_class.is_binary():
                    self._scalers[feature_class.pythonic_name()] = RobustScaler()
                    self._scalers[feature_class.pythonic_name()].fit(
                        train_features[feature_class.pythonic_name()]
                    )
                    train_features[feature_class.pythonic_name()] = self._scalers[
                        feature_class.pythonic_name()
                    ].transform(train_features[feature_class.pythonic_name()])
                    validation_features[feature_class.pythonic_name()] = self._scalers[
                        feature_class.pythonic_name()
                    ].transform(validation_features[feature_class.pythonic_name()])

        input_layers: Dict[str, Input] = {
            train_feature_name: Input(
                shape=train_features[train_feature_name].shape[1:],
                name=train_feature_name,
                dtype=train_feature.dtype,
            )
            for train_feature_name, train_feature in train_features.items()
        }

        input_modalities: List[KerasTensor] = [
            self._build_input_modality(input_layer)
            for input_layer in input_layers.values()
        ]

        hidden: KerasTensor = self._build_hidden_layers(input_modalities)

        hidden = Dense(
            self._dag.number_of_nodes(),
            activation="sigmoid",
            kernel_initializer=GlorotNormal(),
            bias_initializer=LogitBiasInitializer.from_labels(train_labels),
        )(hidden)

        hidden = HarmonizeGraphConvolution(
            supports=[
                self._dag.symmetric_laplacian(),
                self._dag.laplacian(),
                self._dag.transposed_laplacian(),
            ],
            activation="linear",
            learn_support=True,
        )(hidden)

        self._model = Model(
            inputs=input_layers,
            outputs=hidden,
            name="Hammer",
        )

        self._model.compile(
            optimizer=Adam(),
            loss=BinaryFocalCrossentropy(
                apply_class_balancing=True,
            ),
            metrics=get_minimal_multiclass_metrics(),
            jit_compile=False,
        )

        os.makedirs(os.path.dirname(model_checkpoint_path), exist_ok=True)
        learning_rate_scheduler = ReduceLROnPlateau(
            monitor="val_AUPRC",
            factor=0.5,
            patience=20,
            verbose=0,
            mode="max",
            min_delta=1e-4,
            cooldown=3,
            min_lr=1e-6,
        )

        early_stopping = EarlyStopping(
            monitor="val_AUPRC",
            patience=100,
            verbose=0,
            mode="max",
            restore_best_weights=True,
        )

        training_history = self._model.fit(
            train_features,
            train_labels,
            epochs=maximal_number_of_epochs,
            callbacks=[
                TqdmCallback(
                    verbose=1 if self._verbose else 0,
                    leave=False,
                    dynamic_ncols=True,
                ),
                TerminateOnNaN(),
                early_stopping,
                learning_rate_scheduler,
            ],
            batch_size=batch_size,
            shuffle=True,
            verbose=0,
            validation_data=(validation_features, validation_labels),
        )

        self._model.compile(
            optimizer=self._model.optimizer,
            loss=self._model.loss,
            metrics=get_complete_binary_metrics(),
            jit_compile=False,
        )

        return training_history

    def save(self, path: str):
        """Save the classifier model to a file."""
        assert self._model is not None, "Model not trained yet."

        tarball = path.endswith(".tar.gz")

        if path.endswith(".tar.gz"):
            path = path[:-7]

        # We create the directories if they do not exist.
        os.makedirs(path, exist_ok=True)

        dag_path = os.path.join(path, "dag.pkl")
        scalers_path = os.path.join(path, "scalers.pkl")
        spectral_preprocessor_path = os.path.join(path, "spectral_preprocessor.pkl")
        spectral_scaler_path = os.path.join(path, "spectral_scaler.pkl")
        spectral_metadata_extractor_path = os.path.join(
            path, "spectral_metadata_extractor.pkl"
        )

        model_path = os.path.join(path, "model.keras")
        feature_settings_path = os.path.join(path, "feature_settings.json")
        model_plot_path = os.path.join(path, "model.png")

        compress_pickle.dump(self._dag, dag_path)
        compress_pickle.dump(self._scalers, scalers_path)
        compress_pickle.dump(self._spectral_preprocessor, spectral_preprocessor_path)
        if self._spectral_metadata_extractor is not None:
            compress_pickle.dump(
                self._spectral_metadata_extractor, spectral_metadata_extractor_path
            )

        if self._spectral_scaler is not None:
            compress_pickle.dump(self._spectral_scaler, spectral_scaler_path)

        if self._spectral_preprocessor is not None:
            compress_pickle.dump(
                self._spectral_preprocessor, spectral_preprocessor_path
            )

        compress_json.dump(self._feature_settings.to_dict(), feature_settings_path)
        self._model.save(model_path)

        plot_model(
            self._model,
            to_file=model_plot_path,
            show_shapes=True,
            show_dtype=True,
            show_layer_names=True,
            expand_nested=True,
            dpi=100,
            show_layer_activations=True,
            show_trainable=True,
        )

        # We compress the files into a single tar.gz file.
        if tarball:
            os.system(f"tar -czf {path}.tar.gz {path}")
            shutil.rmtree(path)

    def copy(self) -> "Hammer":
        """Return a copy of the classifier model."""
        return deepcopy(self)

    def _samples_to_features(
        self, samples: Union[List[Spectrum], List[str]]
    ) -> Dict[str, np.ndarray]:
        """Transform a list of samples into a dictionary of features."""
        if isinstance(samples[0], Spectrum):
            if (
                self._spectral_preprocessor is None
                or self._spectral_scaler is None
                or self._spectral_metadata_extractor is None
            ):
                raise ValueError("Model has not been trained on spectral data.")
            return {
                "spectra": self._spectral_preprocessor.transform(samples),
                "spectra_binned": self._spectral_scaler.transform(samples),
                **self._spectral_metadata_extractor.transform(samples),
            }
        samples = into_canonical_smiles(
            samples, verbose=self._verbose, n_jobs=self._n_jobs
        )

        features = self._smiles_to_features(samples)

        for feature_class in self._feature_settings.iter_features():
            if not feature_class.is_binary():
                features[feature_class.pythonic_name()] = self._scalers[
                    feature_class.pythonic_name()
                ].transform(features[feature_class.pythonic_name()])

        return features

    def evaluate(
        self, samples: Union[List[Spectrum], List[str]], labels: np.ndarray
    ) -> Dict[str, float]:
        """Evaluate the classifier model."""
        assert self._model is not None, "Model not trained yet."

        evaluations = self._model.evaluate(
            self._samples_to_features(samples), labels, verbose=0, return_dict=True
        )

        return evaluations

    def _samples_to_indices(
        self, samples: Union[List[Spectrum], List[str]]
    ) -> Union[List[str], List[int]]:
        """Transform a list of samples into a list of indices."""
        if isinstance(samples[0], Spectrum):
            name_of_column = None
            for needle in ("feature_id", "smiles", "inchikey"):
                if needle in samples[0].metadata:
                    name_of_column = needle
                    break
            if name_of_column is None:
                warnings.warn(
                    "No column name found in the metadata of some spectra. "
                    "Using the index of the list instead."
                )
                return list(range(len(samples)))

            indices = []

            for sample in samples:
                assert isinstance(sample, Spectrum)
                sample_index = sample.get(name_of_column)
                if sample_index is None:
                    warnings.warn(
                        f"Column '{name_of_column}' not found in the metadata of a spectrum. "
                        "Using the index of the list instead."
                    )
                    return list(range(len(samples)))
                else:
                    indices.append(sample_index)
            return indices

        return samples

    def predict_proba(
        self,
        samples: Union[Spectrum, List[Spectrum], str, List[str]],
    ) -> Dict[str, pd.DataFrame]:
        """Predict the probabilities of the classes."""
        assert self._model is not None, "Model not trained yet."

        if isinstance(samples, (str, Spectrum)):
            samples = [samples]

        features = self._samples_to_features(samples)

        predictions: pd.DataFrame = pd.DataFrame(
            self._model.predict(
                features,
                verbose=1 if self._verbose else 0,
            ),
            columns=self._dag.nodes(),
            index=self._samples_to_indices(samples),
        )

        return {
            layer_name: predictions[self._dag.nodes_in_layer(layer_name)]
            for layer_name in self._dag.layer_names()
        }
