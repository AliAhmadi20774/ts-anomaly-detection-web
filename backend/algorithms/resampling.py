"""Aggregate regularly sampled signals into left-closed time bins."""

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from math import ceil, isfinite
from numbers import Real
from statistics import mean

from algorithms._samples import snapshot_samples


@dataclass(frozen=True, slots=True)
class ResampledSeries:
    """Immutable output rows and their half-open source-sample bounds.

    source_bounds[i] identifies the input rows contributing to values[i]. Bounds
    are local to the supplied input. Divide them by source_sample_rate_hz to get
    time intervals in seconds. The final interval may be shorter than one bin.
    These are contributing sample extents, not nominal bin edges when the rate
    ratio is fractional.
    """

    values: tuple[tuple[float, ...], ...]
    source_bounds: tuple[tuple[int, int], ...]
    source_sample_rate_hz: float
    sample_rate_hz: float


def validate_sample_rate_hz(value, *, name: str) -> None:
    """Require an explicitly supplied, finite positive numeric sampling rate."""
    try:
        valid = type(value) in (int, float) and value > 0 and isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number greater than zero.")


def resampling_ratio(*, source_sample_rate_hz: float, target_sample_rate_hz: float) -> Fraction:
    """Validate rates and return the exact source-to-target decimal rate ratio.

    Aggregation supports equal rates and downsampling. Upsampling needs an
    explicit interpolation policy, which mean/min/max do not provide.
    """
    validate_sample_rate_hz(source_sample_rate_hz, name="source_sample_rate_hz")
    validate_sample_rate_hz(target_sample_rate_hz, name="target_sample_rate_hz")
    source = Fraction(str(source_sample_rate_hz))
    target = Fraction(str(target_sample_rate_hz))
    if target > source:
        raise ValueError("Aggregation cannot upsample; target sample rate must not exceed the source rate.")
    return source / target


def resample_samples(
    samples: Iterable[Iterable[Real]], *, source_sample_rate_hz: float,
    target_sample_rate_hz: float, method: str,
) -> ResampledSeries:
    """Aggregate [sample, feature] rows into bins at the requested sampling rate.

    Sample i has local time i / source_sample_rate_hz. Output bin k covers
    [k / target_rate, (k + 1) / target_rate), anchored at the supplied input's
    start. The reduction is applied independently to each feature, preserving
    column order. Fractional rate ratios are supported without interpolating.

    method is mean, min or max. A final partial bin uses its available samples;
    there is no padding or implicit filtering. Equal rates preserve values.
    Empty input yields no rows, after validating settings. Inputs are copied
    and must contain finite, rectangular numeric rows. Invalid options, samples
    or non-finite calculations raise ValueError before returning.

    source_bounds preserve the actual input extent of each output row, including
    the partial final bin. Time mapping uses the source rate, not the output row
    count. Call separately for different sections; no bin crosses a call boundary.
    """
    ratio = resampling_ratio(
        source_sample_rate_hz=source_sample_rate_hz, target_sample_rate_hz=target_sample_rate_hz,
    )
    if method not in ("mean", "min", "max"):
        raise ValueError("Resampling method must be mean, min or max.")
    matrix = snapshot_samples(samples)
    if ratio == 1:
        return ResampledSeries(
            values=matrix, source_bounds=tuple((index, index + 1) for index in range(len(matrix))),
            source_sample_rate_hz=float(source_sample_rate_hz), sample_rate_hz=float(target_sample_rate_hz),
        )
    values = []
    bounds = []
    # Exact rational boundaries avoid accumulated floating-point drift. A sample
    # on a bin boundary belongs to the next bin, hence ceiling for both edges.
    # Stop at the bin containing the last sample timestamp. Using the signal's
    # nominal duration instead could create a trailing bin with no measurements.
    bin_count = (len(matrix) - 1) // ratio + 1 if matrix else 0
    for bin_index in range(bin_count):
        start = ceil(bin_index * ratio)
        end = min(len(matrix), ceil((bin_index + 1) * ratio))
        row = []
        for feature_index in range(len(matrix[0])):
            column = [matrix[index][feature_index] for index in range(start, end)]
            if method == "mean":
                # The standard-library mean avoids overflowing an intermediate
                # float sum and preserves very small finite measurements.
                reduced = mean(column)
            elif method == "min":
                reduced = min(column)
            else:
                reduced = max(column)
            if not isfinite(reduced):
                raise ValueError(f"Resampling produced a non-finite value in bin {bin_index}.")
            row.append(reduced)
        values.append(tuple(row))
        bounds.append((start, end))
    return ResampledSeries(
        values=tuple(values), source_bounds=tuple(bounds),
        source_sample_rate_hz=float(source_sample_rate_hz), sample_rate_hz=float(target_sample_rate_hz),
    )
