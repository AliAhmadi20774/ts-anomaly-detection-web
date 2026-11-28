"""Execute stored normalization and windowing steps without model inference."""

from collections.abc import Iterable, Iterator
from copy import deepcopy
from numbers import Real

from algorithms._samples import snapshot_samples
from algorithms._specs import validate_input_spec, validate_preprocessing, validate_preprocessing_input
from algorithms.normalization import normalize_samples
from algorithms.windowing import SampleWindow, iter_windows


def _normalize_windows(windows: Iterator[SampleWindow], step: dict) -> Iterator[SampleWindow]:
    """Apply one post-window step lazily while preserving each window's bounds."""
    for window in windows:
        try:
            values = normalize_samples(window.values, step=step)
        except ValueError as error:
            raise ValueError(
                f"Normalization failed for window [{window.start}, {window.end}): {error}"
            ) from error
        yield SampleWindow(start=window.start, end=window.end, values=values)


def iter_preprocessed_windows(
    samples: Iterable[Iterable[Real]], *, preprocessing: dict | None,
    input_spec: dict, stride: int, offset: int = 0,
) -> Iterator[SampleWindow]:
    """Execute a model's ordered preprocessing steps and return complete windows.

    Args:
        samples: Ordered [sample, feature] rows matching input_spec.features.
            Call separately for different serials or sections. The caller must
            supply data at the expected sampling rate; this function cannot
            infer feature names or sampling rate from numeric rows.
        preprocessing: The stored schema-1 declaration. Execution requires
            exactly one window step and supports normalize steps on either side.
        input_spec: The model's ordered feature names and optional sample rate.
        stride: Distance between window starts, supplied by analysis settings.
        offset: Non-negative sample index added to output bounds.

    Returns:
        An iterator of immutable SampleWindow objects, preserving sample bounds.
        Settings are validated and copied, and samples are snapshotted, before
        returning. Post-window normalization executes as windows are consumed;
        its arithmetic errors are raised during iteration. Empty input yields
        no windows after validation. Neither samples nor settings are modified.

    Raises:
        ValueError: For missing/invalid metadata, invalid runtime options,
            mismatched features, missing windowing, or invalid measurements.
        NotImplementedError: If the declaration contains a resample step.

    No implicit normalization, resampling, padding, training or tensor conversion
    is performed. Steps retain their declared order, including multiple distinct
    normalization steps before or after windowing.
    """
    if preprocessing is None:
        raise ValueError("Model preprocessing is not configured.")
    validate_preprocessing(preprocessing)
    validate_input_spec(input_spec)
    validate_preprocessing_input(preprocessing, input_spec)
    if type(stride) is not int or stride < 1:
        raise ValueError("stride must be a positive integer.")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer.")

    # Freeze the plan so later caller changes cannot affect lazy transformations.
    steps = deepcopy(preprocessing["steps"])
    if any(step["type"] == "resample" for step in steps):
        raise NotImplementedError("Resampling is not supported by the preprocessing executor yet.")
    window_index = next((index for index, step in enumerate(steps) if step["type"] == "window"), None)
    if window_index is None:
        raise ValueError("The preprocessing executor requires exactly one window step.")

    # Validate all measurements, even those excluded later by a drop tail policy.
    matrix = snapshot_samples(samples)
    if matrix and len(matrix[0]) != len(input_spec["features"]):
        raise ValueError("Sample feature count must match input_spec.features.")
    for step in steps[:window_index]:
        matrix = normalize_samples(matrix, step=step)

    window_step = steps[window_index]
    windows = iter_windows(
        matrix, window_size=window_step["size"], stride=stride,
        tail=window_step["tail"], offset=offset,
    )
    # Each wrapper captures its own step, preserving order without constructing
    # all overlapping windows in memory at once.
    for step in steps[window_index + 1:]:
        windows = _normalize_windows(windows, step)
    return windows
