"""Build the LSTM-AE parameter topology and load compatible tensor weights."""

from dataclasses import dataclass
from pickle import UnpicklingError
from typing import BinaryIO

import torch
from torch import nn

from algorithms._specs import validate_input_spec, validate_json_object
from algorithms.runtimes.torch_device import get_torch_device


@dataclass(frozen=True, slots=True)
class LSTMArchitecture:
    """Architecture settings stored with a trained LSTM-AE version."""

    hidden_size: int
    num_layers: int
    dropout: float


def _architecture(params: dict) -> LSTMArchitecture:
    validate_json_object(params)
    if set(params) != {"hidden_size", "num_layers", "dropout"}:
        raise ValueError("LSTM architecture requires exactly hidden_size, num_layers and dropout.")
    for name in ("hidden_size", "num_layers"):
        if type(params[name]) is not int or params[name] < 1:
            raise ValueError(f"{name} must be a positive integer.")
    dropout = params["dropout"]
    if type(dropout) not in (int, float) or not 0 <= dropout <= 1:
        raise ValueError("dropout must be a finite number between zero and one.")
    return LSTMArchitecture(params["hidden_size"], params["num_layers"], float(dropout))


class LSTMAutoencoder(nn.Module):
    """Parameter graph for two unidirectional LSTMs and a linear decoder head.

    Feature count comes from input_spec, independently of the hidden size.
    Module names match the checkpoint's parameter names; no old project code is
    imported. This loading stage does not choose an encoder-state initialization
    or decoding policy. Reconstruction will be implemented separately.
    """

    algorithm_key = "lstm_ae"

    def __init__(self, architecture: LSTMArchitecture, features: tuple[str, ...]):
        super().__init__()
        self.architecture = architecture
        self.features = features
        # PyTorch applies LSTM dropout between stacked layers only. Preserve the
        # declared setting, while avoiding a meaningless single-layer warning.
        effective_dropout = architecture.dropout if architecture.num_layers > 1 else 0.0
        options = {
            "input_size": len(features), "hidden_size": architecture.hidden_size,
            "num_layers": architecture.num_layers, "dropout": effective_dropout,
            "batch_first": True, "bias": True,
            "device": "cpu", "dtype": torch.float32,
        }
        self.encoder = nn.ModuleDict({"lstm": nn.LSTM(**options)})
        self.decoder = nn.ModuleDict({
            "lstm": nn.LSTM(**options),
            "linear": nn.Linear(architecture.hidden_size, len(features), device="cpu", dtype=torch.float32),
        })

    @property
    def device(self) -> torch.device:
        """The actual model device; inference inputs must use this same device."""
        return next(self.parameters()).device

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError("Reconstruction execution is not implemented in the model-loading stage.")


def _validate_weights(state: dict, architecture: LSTMArchitecture, feature_count: int) -> None:
    """Check compatibility before allocating a model from database dimensions."""
    if not isinstance(state, dict) or len(state) != 8 * architecture.num_layers + 2:
        raise ValueError("Checkpoint keys do not match the configured LSTM architecture.")
    shapes = {}
    hidden_size = architecture.hidden_size
    for component in ("encoder", "decoder"):
        for layer in range(architecture.num_layers):
            input_size = feature_count if layer == 0 else hidden_size
            prefix = f"{component}.lstm."
            shapes[f"{prefix}weight_ih_l{layer}"] = (4 * hidden_size, input_size)
            shapes[f"{prefix}weight_hh_l{layer}"] = (4 * hidden_size, hidden_size)
            shapes[f"{prefix}bias_ih_l{layer}"] = (4 * hidden_size,)
            shapes[f"{prefix}bias_hh_l{layer}"] = (4 * hidden_size,)
    shapes["decoder.linear.weight"] = (feature_count, hidden_size)
    shapes["decoder.linear.bias"] = (feature_count,)
    if set(state) != set(shapes):
        raise ValueError("Checkpoint keys do not match the configured LSTM architecture.")
    for name, shape in shapes.items():
        tensor = state[name]
        if not isinstance(tensor, torch.Tensor) or tuple(tensor.shape) != shape:
            raise ValueError(f"Weight {name} has an incompatible shape; expected {shape}.")
        if tensor.layout != torch.strided or tensor.device.type != "cpu" or tensor.dtype != torch.float32:
            raise ValueError(f"Weight {name} must be a dense CPU float32 tensor.")
        if not torch.isfinite(tensor).all().item():
            raise ValueError(f"Weight {name} contains non-finite values.")


def load_lstm_ae(source: BinaryIO, *, architecture_params: dict, input_spec: dict) -> LSTMAutoencoder:
    """Load weights and place the model on an available CUDA GPU or CPU.

    Accept either a tensor state dictionary or a training checkpoint containing
    model_state_dict. Other training entries are ignored. Deserialization always
    uses weights_only=True; unsupported serialized objects are rejected without
    falling back to unrestricted pickle loading.

    Metadata, exact keys, shapes, float32 dtypes and finite values must agree.
    Successful loading returns an evaluation-mode model with gradients disabled.
    Input metadata and source bytes are unchanged. Invalid metadata or checkpoint
    content raises ValueError. The caller owns and closes the stream.
    """
    architecture = _architecture(architecture_params)
    validate_input_spec(input_spec)
    features = tuple(input_spec["features"])
    try:
        checkpoint = torch.load(source, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, EOFError, ValueError, TypeError, UnpicklingError) as error:
        raise ValueError("Weights file is not a supported tensor checkpoint.") from error
    if not isinstance(checkpoint, dict):
        raise ValueError("Weights file must contain a tensor state dictionary.")
    state = checkpoint.get("model_state_dict", checkpoint)
    _validate_weights(state, architecture, len(features))
    # Construction initializes temporary parameters. Preserve the caller's CPU
    # RNG state because every parameter will be replaced with trained weights.
    with torch.random.fork_rng(devices=[]):
        model = LSTMAutoencoder(architecture, features)
    model.load_state_dict(state, strict=True)
    model.eval()
    model.requires_grad_(False)
    # Validate the checkpoint on CPU first. Transfer only the model's weights,
    # not unrelated training data such as optimizer state, to the selected GPU.
    device = get_torch_device()
    try:
        model.to(device)
    except RuntimeError as error:
        raise ValueError(f"Could not place the model on {device}: {error}") from error
    return model
