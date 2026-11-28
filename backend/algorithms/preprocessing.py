"""Execute stored preprocessing steps while preserving original sample bounds."""

from collections.abc import Iterable, Iterator
from copy import deepcopy
from numbers import Real

from algorithms._samples import snapshot_samples
from algorithms._specs import validate_input_spec, validate_preprocessing, validate_preprocessing_input
from algorithms.normalization import normalize_samples
from algorithms.resampling import resample_samples, resampling_ratio, validate_sample_rate_hz
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


def _source_windows(
    windows: Iterator[SampleWindow], source_bounds: tuple[tuple[int, int], ...], offset: int,
) -> Iterator[SampleWindow]:
    """Map processed window indices back to the original input sample domain."""
    for window in windows:
        yield SampleWindow(
            start=offset + source_bounds[window.start][0],
            end=offset + source_bounds[window.end - 1][1], values=window.values,
        )


def iter_preprocessed_windows(
    samples: Iterable[Iterable[Real]], *, preprocessing: dict | None,
    input_spec: dict, stride: int, offset: int = 0, source_sample_rate_hz: float | None = None,
) -> Iterator[SampleWindow]:
    """Execute a model's ordered preprocessing steps and return complete windows.

    Args:
        samples: Ordered [sample, feature] rows matching input_spec.features.
            Call separately for different serials or sections. The caller must
            supply the correct feature order; numeric rows cannot identify it.
        preprocessing: The stored schema-1 declaration. Execution requires
            exactly one window step and supports normalize steps on either side.
        input_spec: The model's ordered feature names and optional sample rate.
        stride: Distance between window starts, supplied by analysis settings.
        offset: Non-negative sample index added to output bounds.
        source_sample_rate_hz: Actual input rate, required for resampling. Without
            resampling, a supplied rate must match input_spec.sample_rate_hz when
            declared; omission retains the caller's responsibility for the rate.

    Returns:
        An iterator of immutable SampleWindow objects in the ORIGINAL sample
        index domain, plus offset. Divide bounds by the source sampling rate to
        obtain seconds. With resampling, end - start need not equal len(values).
        Settings are validated and copied, and samples are snapshotted, before
        returning. Post-window normalization executes as windows are consumed;
        its arithmetic errors are raised during iteration. Empty input yields
        no windows after validation. Neither samples nor settings are modified.

    Raises:
        ValueError: For missing/invalid metadata, invalid runtime options,
            mismatched features, missing windowing, or invalid measurements.

    Resampling uses input_spec.sample_rate_hz as the target and must precede
    windowing. Window size and stride count PROCESSED samples. No implicit
    resampling, padding, training or tensor conversion is performed. Steps retain
    their declared order, including normalization before or after resampling.
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
    has_resampling = any(step["type"] == "resample" for step in steps)
    target_rate = input_spec.get("sample_rate_hz")
    if source_sample_rate_hz is not None:
        validate_sample_rate_hz(source_sample_rate_hz, name="source_sample_rate_hz")
    if has_resampling:
        if source_sample_rate_hz is None:
            raise ValueError("source_sample_rate_hz is required for resampling.")
        resampling_ratio(source_sample_rate_hz=source_sample_rate_hz, target_sample_rate_hz=target_rate)
    elif source_sample_rate_hz is not None and target_rate is not None and source_sample_rate_hz != target_rate:
        raise ValueError("Source and model sample rates differ; declare a resample step.")
    window_index = next((index for index, step in enumerate(steps) if step["type"] == "window"), None)
    if window_index is None:
        raise ValueError("The preprocessing executor requires exactly one window step.")

    # Validate all measurements, even those excluded later by a drop tail policy.
    matrix = snapshot_samples(samples)
    if matrix and len(matrix[0]) != len(input_spec["features"]):
        raise ValueError("Sample feature count must match input_spec.features.")
    source_bounds = None
    current_rate = source_sample_rate_hz
    for step in steps[:window_index]:
        if step["type"] == "normalize":
            matrix = normalize_samples(matrix, step=step)
        else:
            resampled = resample_samples(
                matrix, source_sample_rate_hz=current_rate,
                target_sample_rate_hz=target_rate, method=step["method"],
            )
            if source_bounds is None:
                source_bounds = resampled.source_bounds
            else:
                source_bounds = tuple(
                    (source_bounds[start][0], source_bounds[end - 1][1])
                    for start, end in resampled.source_bounds
                )
            matrix = resampled.values
            current_rate = target_rate

    window_step = steps[window_index]
    windows = iter_windows(
        matrix, window_size=window_step["size"], stride=stride,
        tail=window_step["tail"], offset=0 if has_resampling else offset,
    )
    if source_bounds is not None:
        windows = _source_windows(windows, source_bounds, offset)
    # Each wrapper captures its own step, preserving order without constructing
    # all overlapping windows in memory at once.
    for step in steps[window_index + 1:]:
        windows = _normalize_windows(windows, step)
    return windows
