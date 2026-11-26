"""Window numeric samples independently of storage, algorithms and frameworks."""

from collections.abc import Iterable, Iterator, Mapping, Set
from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True, slots=True)
class SampleWindow:
    """Immutable values and input-sample bounds, with an exclusive end index."""

    start: int
    end: int
    values: tuple[tuple[float, ...], ...]


def _snapshot(samples: Iterable[Iterable[Real]]) -> tuple[tuple[float, ...], ...]:
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

    Validate and snapshot input before returning an iterator. Window values use
    immutable rows so overlapping windows cannot change each other or the source.
    `drop` ignores an incomplete tail; `reject` requires the last complete window
    to reach the end of a non-empty input. Empty input always yields no windows.
    Bounds use the supplied samples' index domain plus `offset`; callers handle
    section selection, resampling/time mapping and conversion to model tensors.
    """
    for name, value in (("window_size", window_size), ("stride", stride)):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer.")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer.")
    if tail not in ("drop", "reject"):
        raise ValueError("tail must be drop or reject.")
    matrix = _snapshot(samples)
    count = max(0, (len(matrix) - window_size) // stride + 1)
    last_end = (count - 1) * stride + window_size if count else 0
    if tail == "reject" and matrix and last_end != len(matrix):
        raise ValueError("Input has an incomplete tail for this window size and stride.")
    return (
        SampleWindow(offset + start, offset + start + window_size, matrix[start:start + window_size])
        for start in range(0, count * stride, stride)
    )
