"""
Signal processing and preprocessing module for time series data.

This module provides functions for:
- Creating windowed sequences from data
- Combining multivariate time series
- Applying transformations (mean, max, min) and resampling

Functions:
    create_seq: Create windowed sequences from DataFrame
    regroup_multivariate_ts: Combine multiple time series into a 3D array
    preprocessing: Apply transformations and resampling to data
    preprocessing_with_bounds: Also return window bounds in original samples
"""

import numpy as np
import pandas as pd
from typing import List, Tuple

def create_seq(data: pd.DataFrame, step_window: int, size_window: int) -> np.ndarray:
    """
    Take a pandas DataFrame with time index as input and return a (size_window * )
    return numpy array of ((size_ts-size_window) / step_window, size_window)
    """
    time_lenght, nb_time_series = data.shape
    additional_ts = len(range(0, time_lenght - size_window + 1, step_window))
    output = np.zeros((nb_time_series, additional_ts, size_window))
    seq = pd.DataFrame(data.iloc[:size_window, 0])
    for j, shift_value in enumerate(
        range(0, time_lenght - size_window + 1, step_window)
    ):
        data_shift = data.shift(-shift_value)
        for i in range(0, nb_time_series):
            output[i, j, :] = data_shift.iloc[:size_window, i]
    return output.reshape(-1, size_window)

def regroup_multivariate_ts(list_ts: List[np.ndarray]) -> np.ndarray:
    """
    Create a 3 dimensional array from a list of time serie of same size
    :list_ts: list of 2 dimensional time series sequence to concatenate in a third dimension
    """
    global_array = np.empty(
        shape=(list_ts[0].shape[0], list_ts[0].shape[1], len(list_ts))
    )
    for i, ts in enumerate(list_ts):
        global_array[:, :, i] = ts
    return global_array

def preprocessing_with_bounds(
    input_df: pd.DataFrame,
    list_transfo: List[str],
    resample_freq: str,
    size_window: int,
    step_window: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return model windows and their [start, end) bounds in original samples.

    Bounds are relative to the input section and shared by all input signals.
    Windows retain signal-major order: all windows of the first signal, then
    all windows of the next signal. Derive bounds from the actual resampled
    time bins so fractional periods and the final partial bin stay aligned.
    """
    data = input_df.copy()
    data = data.T
    data.index = pd.date_range(start="1/1/2018", periods=input_df.shape[1], freq="ms")
    period = pd.Timedelta(resample_freq + "ms")
    resampler = data.resample(resample_freq + "ms")
    list_var = []
    resampled = None
    for transformation in ("mean", "max", "min", "raw"):
        if transformation in list_transfo:
            aggregation = "mean" if transformation == "raw" else transformation
            resampled = getattr(resampler, aggregation)()
            list_var.append(create_seq(resampled, step_window, size_window))

    if resampled is None:
        raise ValueError("At least one supported signal transformation is required")

    window_starts = np.arange(0, len(resampled) - size_window + 1, step_window)
    start_times = resampled.index[window_starts]
    end_times = resampled.index[window_starts + size_window - 1] + period
    window_bounds = np.column_stack((
        data.index.searchsorted(start_times, side="left"),
        data.index.searchsorted(end_times, side="left"),
    ))
    return regroup_multivariate_ts(list_var), window_bounds


def preprocessing(input_df: pd.DataFrame, list_transfo: List[str], resample_freq: str, size_window: int, step_window: int) -> np.ndarray:
    """Return model windows, preserving the existing preprocessing interface."""
    windows, _ = preprocessing_with_bounds(
        input_df, list_transfo, resample_freq, size_window, step_window,
    )
    return windows


