"""Positional encoder layer for a Transformer Layer, for a given spectrum."""

from keras import ops  # type: ignore
from keras import KerasTensor
from keras.api.layers import Layer  # type: ignore
from keras.api.utils import register_keras_serializable  # type: ignore


@register_keras_serializable(package="hammer")
class SinePositionEncoding(Layer):
    """Sinusoidal positional encoding layer.

    This layer calculates the position encoding as a mix of sine and cosine
    functions with geometrically increasing wavelengths. Defined and formulized
    in [Attention is All You Need](https://arxiv.org/abs/1706.03762).

    Takes as input an embedded token tensor. The input must have shape
    [batch_size, sequence_length, feature_size]. This layer will return a
    positional encoding the same size as the embedded token tensor, which
    can be added directly to the embedded token tensor.

    Args:
        max_wavelength: The maximum angular wavelength of the sine/cosine
            curves, as described in Attention is All You Need. Defaults to
            `10000`.
        **kwargs: other keyword arguments passed to `keras.layers.Layer`,
            including `name`, `trainable`, `dtype` etc.

    Call arguments:
        inputs: The tensor inputs to compute an embedding for, with shape
            `(batch_size, sequence_length, hidden_dim)`.
        start_index: An integer or integer tensor. The starting position to
            compute the encoding from. This is useful during cached decoding,
            where each position is predicted separately in a loop.

    Example:
    ```python
    # create a simple embedding layer with sinusoidal positional encoding
    seq_len = 100
    vocab_size = 1000
    embedding_dim = 32
    inputs = keras.Input((seq_len,), dtype="float32")
    embedding = keras.layers.Embedding(
        input_dim=vocab_size, output_dim=embedding_dim
    )(inputs)
    positional_encoding = keras_hub.layers.SinePositionEncoding()(embedding)
    outputs = embedding + positional_encoding
    ```

    References:
     - [Vaswani et al., 2017](https://arxiv.org/abs/1706.03762)
    """

    def __init__(
        self,
        max_wavelength=10000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.max_wavelength = max_wavelength
        self.built = True

    # pylint: disable=arguments-differ
    def call(self, inputs, start_index=0) -> KerasTensor:
        """Compute the positional encoding for the input tensor."""
        shape = ops.shape(inputs)
        seq_length = shape[-2]
        hidden_size = shape[-1]
        positions = ops.arange(seq_length)
        positions = ops.cast(positions + start_index, self.compute_dtype)
        min_freq = ops.cast(1 / self.max_wavelength, dtype=self.compute_dtype)
        timescales = ops.power(
            min_freq,
            ops.cast(2 * (ops.arange(hidden_size) // 2), self.compute_dtype)
            / ops.cast(hidden_size, self.compute_dtype),
        )
        angles = ops.expand_dims(positions, 1) * ops.expand_dims(timescales, 0)
        # even indices are sine, odd are cosine
        cos_mask = ops.cast(ops.arange(hidden_size) % 2, self.compute_dtype)
        sin_mask = 1 - cos_mask
        # embedding shape is [seq_length, hidden_size]
        positional_encodings = ops.sin(angles) * sin_mask + ops.cos(angles) * cos_mask

        return ops.broadcast_to(positional_encodings, shape)

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "max_wavelength": self.max_wavelength,
            }
        )
        return config

    # pylint: disable=arguments-differ
    def compute_output_shape(self, input_shape):
        """Return the input shape."""
        return input_shape

    def _serialize_to_tensors(self) -> dict:
        """Handle serialization to tensors (needed for checkpointing)."""
        return {}

    def _restore_from_tensors(self, restored_tensors: dict) -> None:
        """Handle restoration from tensors (needed for checkpointing)."""

    def add_metric(self, *args, **kwargs) -> None:
        """Add a metric to the layer (not used in this layer)."""
        # This is a placeholder since we are not adding any custom metrics in this layer
