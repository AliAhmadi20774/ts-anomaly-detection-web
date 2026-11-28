"""Batch reconstruction and scoring shared by PyTorch autoencoders."""

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True, slots=True)
class ReconstructionResult:
    """Mean reconstruction, per-window MSE and the repeat count actually used.

    reconstruction has shape [batch, sample, feature]; scores has shape [batch].
    Both tensors stay on the input/model device and have no autograd graph.
    The repeat count is execution metadata, not a model architecture setting.
    """

    reconstruction: torch.Tensor
    scores: torch.Tensor
    reconstruction_repeats: int


def validate_reconstruction_repeats(value: int) -> None:
    """Require a positive integer; booleans are not valid repeat counts."""
    if type(value) is not int or value < 1:
        raise ValueError("reconstruction_repeats must be a positive integer.")


@torch.inference_mode()
def reconstruct_batch(
    model: nn.Module, inputs: torch.Tensor, *, reconstruction_repeats: int = 10,
) -> ReconstructionResult:
    """Average repeated reconstructions, then calculate MSE per window.

    inputs must already match the model's device and dtype. Evaluation mode
    disables dropout; explicit randomness inside a model remains active. No
    seed is set here. The caller controls batch size and any reproducibility
    policy. Process batches separately to bound GPU memory use.

    Accumulate one output at a time instead of keeping all repeated outputs.
    Scaling each contribution avoids an unscaled sum proportional to repeats.
    Floating-point results can differ slightly from stacking and averaging.
    No model weights, input values or database records are modified.
    """
    validate_reconstruction_repeats(reconstruction_repeats)
    if not isinstance(inputs, torch.Tensor) or inputs.ndim != 3 or any(size == 0 for size in inputs.shape):
        raise ValueError("inputs must be a non-empty [batch, sample, feature] tensor.")
    parameter = next(model.parameters())
    if inputs.device != parameter.device or inputs.dtype != parameter.dtype:
        raise ValueError("inputs must match the model's device and dtype.")
    if inputs.layout != torch.strided or not inputs.is_floating_point() or not torch.isfinite(inputs).all().item():
        raise ValueError("inputs must contain dense, finite floating-point values.")

    model.eval()
    reconstruction = torch.zeros_like(inputs)
    for _ in range(reconstruction_repeats):
        output = model(inputs)
        if not isinstance(output, torch.Tensor) or output.shape != inputs.shape:
            raise ValueError("Model reconstruction must be a tensor with the input shape.")
        if output.device != inputs.device or output.dtype != inputs.dtype or output.layout != torch.strided:
            raise ValueError("Model reconstruction must match the input device, dtype and dense layout.")
        if not torch.isfinite(output).all().item():
            raise ValueError("Model reconstruction contains non-finite values.")
        reconstruction.add_(output, alpha=1.0 / reconstruction_repeats)

    if not torch.isfinite(reconstruction).all().item():
        raise ValueError("Mean reconstruction contains non-finite values.")
    scores = (inputs - reconstruction).square().mean(dim=(1, 2))
    if not torch.isfinite(scores).all().item():
        raise ValueError("Reconstruction MSE is non-finite; check input scaling.")
    return ReconstructionResult(reconstruction, scores, reconstruction_repeats)
