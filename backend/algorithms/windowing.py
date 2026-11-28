"""Window numeric samples independently of storage, algorithms and frameworks."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from numbers import Real

from algorithms._samples import snapshot_samples


@dataclass(frozen=True, slots=True)
class SampleWindow:
    """A complete window with immutable values and half-open bounds [start, end).

    Each row in ``values`` is one sample; columns preserve the input feature order.
    Bounds identify samples in the caller's index domain, including any offset.
    """

    start: int
    end: int
    values: tuple[tuple[float, ...], ...]


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
    matrix = snapshot_samples(samples)

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
