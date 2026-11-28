"""Shared device selection for PyTorch algorithm loaders."""

import torch


def get_torch_device() -> torch.device:
    """Prefer the first visible CUDA GPU; use CPU when CUDA is unavailable.

    Availability is checked inside the running process, including its installed
    PyTorch build, drivers and container device access. CUDA_VISIBLE_DEVICES can
    restrict which server GPUs this process sees.
    """
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
