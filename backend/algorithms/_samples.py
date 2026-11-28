"""Shared validation for ordered [sample, feature] matrices."""

from collections.abc import Iterable, Mapping, Set
from math import isfinite
from numbers import Real


def snapshot_samples(samples: Iterable[Iterable[Real]]) -> tuple[tuple[float, ...], ...]:
    """Validate feature rows and copy them into immutable finite floats.

    Every row must contain the same non-zero number of features. Copying the
    input once prevents later source changes from affecting returned results.
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
