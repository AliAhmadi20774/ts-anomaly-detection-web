"""
Inference module for anomaly detection models.

This module provides functions for:
- Computing average model predictions over multiple runs
- Calculating reconstruction error for each window
- Reconstructing original time series from windowed data

Functions:
    get_avg_pred: Compute average model output and reconstruction error
    get_original_ts: Reconstruct original time series from windowed data
"""

import torch
from torch.utils.data import DataLoader
from typing import Tuple


def get_avg_pred(
    loader: DataLoader,
    input_data: torch.Tensor,
    model: torch.nn.Module,
    seq_length: int,
    device: torch.device,
    epoch: int = 10,
    cancel_fn=None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    predict = torch.zeros(size=input_data.shape, dtype=torch.float)

    # error
    reconstruction_error = torch.zeros(size=(input_data.shape[0],), dtype=torch.float)
    criterion_seq = torch.nn.MSELoss(reduction="none")

    idx = 0

    with torch.no_grad():
        for id_batch, data in enumerate(loader):
            if cancel_fn and cancel_fn():
                raise InterruptedError("Inference cancelled")

            data = data.to(device)

            outputs = []
            for _ in range(epoch):
                if cancel_fn and cancel_fn():
                    raise InterruptedError("Inference cancelled")
                output = model.forward(data)
                outputs.append(output)

            avg_output = torch.stack(outputs).mean(dim=0)

            bs = data.shape[0]

            output_seq = avg_output.reshape(bs, seq_length, -1).to(device)
            predict[idx : idx + bs, :, :] = output_seq.detach().cpu()

            # error per seq
            data_seq = data.reshape(bs, seq_length, -1)
            loss_none = criterion_seq(data_seq, output_seq)
            error_per_seq = loss_none.mean(dim=[1, 2])
            reconstruction_error[idx : idx + bs] = error_per_seq.detach().cpu()
            idx += bs

    return predict, reconstruction_error


def get_original_ts(
    data: torch.Tensor,
    size_window: int,
    step_window: int,
    nb_ts_origine: int,
    nb_feature: int,
) -> torch.Tensor:
    """
    Recreate the original time serie leaving the overlapping part of the seq since the last part are the beginning of the decoding.
    Keeping the first element gives more potential error on prediction.
    """
    last_values = size_window - step_window

    return torch.cat(
        (
            data[:, :step_window, :].reshape(nb_ts_origine, -1, nb_feature),
            data.reshape(nb_ts_origine, -1, nb_feature)[:, -last_values:, :],
        ),
        axis=1,
    )
