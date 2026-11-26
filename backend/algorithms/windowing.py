"""Window numeric samples independently of storage, algorithms and frameworks."""

from collections.abc import Iterable, Iterator, Mapping, Set
from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True, slots=True)
class SampleWindow:
    """A complete window with immutable values and half-open bounds [start, end).

    Each row in ``values`` is one sample; columns preserve the input feature order.
    Bounds identify samples in the caller's index domain, including any offset.
    """

    start: int
    end: int
    values: tuple[tuple[float, ...], ...]


def _snapshot(samples: Iterable[Iterable[Real]]) -> tuple[tuple[float, ...], ...]:
    """Validate ordered feature rows and copy them into immutable finite floats.

    Every row must contain the same non-zero number of features. Copying the
    input once prevents later source changes from affecting returned windows.
    """
    # Text, mappings and sets do not represent ordered numeric sample rows.
    if isinstance(samples, (str, bytes, bytearray, Mapping, Set)):
        raise ValueError("samples must contain rows of numeric feature values.")
    try:
        rows = iter(samples)
    except TypeError as error:
        raise ValueError("samples must be an iterable of feature rows.") from error
    snapshot = []
    width = None
    for index, row in enumerate(rows):
        if isinstance(row, (str, bytes, bytearray, Mapping, Set)):
            raise ValueError(f"Sample {index} must be a numeric feature row.")
        try:
            values = tuple(row)
        except TypeError as error:
            raise ValueError(f"Sample {index} must be a numeric feature row.") from error
        if not values or (width is not None and len(values) != width):
            raise ValueError("All samples must have the same non-zero number of features.")
        converted = []
        for value in values:
            # Python treats bool as a number, but it is not a signal measurement.
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"Sample {index} contains a non-numeric feature.")
            try:
                numeric = float(value)
            except (ValueError, OverflowError) as error:
                raise ValueError(f"Sample {index} cannot be represented as finite floats.") from error
            if not isfinite(numeric):
                raise ValueError(f"Sample {index} contains a non-finite feature.")
            converted.append(numeric)
        snapshot.append(tuple(converted))
        width = len(values)
    return tuple(snapshot)


def iter_windows(
    samples: Iterable[Iterable[Real]], *, window_size: int, stride: int,
    tail: str, offset: int = 0,
) -> Iterator[SampleWindow]:
    """Return complete windows in time order from [sample, feature] rows.

    Args:
        samples: Ordered rows of numeric feature values, one row per sample.
        window_size: Number of samples in each complete window.
        stride: Distance in samples between consecutive window starts. A stride
            smaller than window_size creates overlap; a larger one leaves gaps.
        tail: "drop" ignores an incomplete tail. "reject" requires the last
            complete window to reach the end of a non-empty input.
        offset: Non-negative index added to window bounds, without changing values.

    Returns:
        An iterator of immutable SampleWindow objects. Empty input yields no
        windows. Input is validated and copied before the iterator is returned.

    Raises:
        ValueError: If options or sample values are invalid, or tail="reject"
            leaves a non-empty input without a complete window ending at its end.

    For example, six samples with window_size=4 and stride=2 produce bounds
    [0, 4) and [2, 6). With offset=100, these become [100, 104) and [102, 106).
    Bounds refer to the supplied samples, not timestamps. Callers handle section
    selection, resampling/time mapping and conversion to model tensors.
    """
    for name, value in (("window_size", window_size), ("stride", stride)):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer.")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer.")
    if tail not in ("drop", "reject"):
        raise ValueError("tail must be drop or reject.")

    # Snapshot eagerly so invalid input fails now, before iteration starts.
    matrix = _snapshot(samples)

    # Complete windows satisfy start + window_size <= sample count. Floor
    # division counts the valid stride steps after the first window; clamp to
    # zero when the input is shorter than one window.
    count = max(0, (len(matrix) - window_size) // stride + 1)
    last_end = (count - 1) * stride + window_size if count else 0
    if tail == "reject" and matrix and last_end != len(matrix):
        raise ValueError("Input has an incomplete tail for this window size and stride.")

    # Build windows lazily from the snapshot. Offset affects only the reported
    # bounds; slicing always uses local indices and an exclusive end index.
    return (
        SampleWindow(offset + start, offset + start + window_size, matrix[start:start + window_size])
        for start in range(0, count * stride, stride)
    )
