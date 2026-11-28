"""Shared device selection and input transfer for PyTorch algorithms."""

import numpy as np
import torch
from torch import nn


def get_torch_device() -> torch.device:
    """Prefer the first visible CUDA GPU; use CPU when CUDA is unavailable.

    Availability is checked inside the running process, including its installed
    PyTorch build, drivers and container device access. CUDA_VISIBLE_DEVICES can
    restrict which server GPUs this process sees.
    """
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def as_numeric_tensor(data) -> torch.Tensor:
    """Read lists, NumPy arrays or tensors without selecting a new device.

    Existing tensors retain their current device. Each algorithm can validate
    its required shape before allocating input memory on the model's GPU.
    """
    try:
        # Python floats are double precision. NumPy preserves them until the
        # explicit model-dtype conversion, independently of PyTorch defaults.
        source = data if isinstance(data, torch.Tensor) else np.asarray(data)
        inputs = torch.as_tensor(source)
    except (TypeError, ValueError, RuntimeError, OverflowError) as error:
        raise ValueError("Input data must be a rectangular numeric batch.") from error
    if inputs.layout != torch.strided or inputs.dtype == torch.bool or inputs.is_complex():
        raise ValueError("Input data must contain dense, real numeric values.")
    return inputs


def to_model_tensor(inputs: torch.Tensor, *, model: nn.Module) -> torch.Tensor:
    """Transfer a validated batch to the actual parameter device and dtype.

    Detach training graphs without modifying the input. Report transfer failures
    without a device fallback. The caller validates the algorithm's input shape
    before calling this function.
    """
    parameter = next(model.parameters())
    try:
        inputs = inputs.detach().to(device=parameter.device, dtype=parameter.dtype)
    except (RuntimeError, OverflowError) as error:
        raise ValueError(f"Could not place input data on {parameter.device}: {error}") from error
    # Conversion to the model's dtype can overflow even when source values are
    # finite. Validate the actual tensor that will be consumed by the model.
    if not torch.isfinite(inputs).all().item():
        raise ValueError("Input data must remain finite in the model's dtype.")
    return inputs
