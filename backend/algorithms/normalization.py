"""Apply externally fitted normalization without learning from new samples."""

from collections.abc import Iterable
from math import isfinite
from numbers import Real

from algorithms._samples import snapshot_samples


def _finite_number(value) -> bool:
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def _require_fields(step: dict, expected: set[str]) -> None:
    if set(step) != expected:
        raise ValueError(f"Expected exactly these fields: {', '.join(sorted(expected))}.")


def _validate_vector(value, name: str, *, positive: bool = False) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty numeric list in input feature order.")
    if not all(_finite_number(item) and (not positive or item > 0) for item in value):
        raise ValueError(f"{name} must contain finite {'positive ' if positive else ''}numbers.")


def validate_normalization(step: dict) -> None:
    """Validate one schema-1 normalization step independently of Django.

    Both metadata validation and execution use these rules. Vector lengths must
    agree here; the caller also checks them against the actual input features.
    """
    if not isinstance(step, dict) or step.get("type") != "normalize":
        raise ValueError("Provide a normalization step with type normalize.")
    method = step.get("method")
    if method == "none":
        _require_fields(step, {"type", "method"})
    elif method == "standardize":
        _require_fields(step, {"type", "method", "mean", "scale"})
        _validate_vector(step["mean"], "mean")
        _validate_vector(step["scale"], "scale", positive=True)
        if len(step["mean"]) != len(step["scale"]):
            raise ValueError("mean and scale must have the same length.")
    elif method == "minmax":
        _require_fields(step, {"type", "method", "scale", "offset", "range", "clip"})
        _validate_vector(step["scale"], "scale")
        _validate_vector(step["offset"], "offset")
        _validate_vector(step["range"], "range")
        if len(step["scale"]) != len(step["offset"]) or any(scale < 0 for scale in step["scale"]):
            raise ValueError("Min-max scale and offset must have equal lengths and scales must be non-negative.")
        bounds = step["range"]
        if len(bounds) != 2 or bounds[1] <= bounds[0] or not _finite_number(bounds[1] - bounds[0]):
            raise ValueError("range must contain an increasing pair with a finite positive span.")
        if type(step["clip"]) is not bool:
            raise ValueError("clip must be true or false.")
    else:
        raise ValueError("Normalization method must be none, standardize or minmax.")


def normalize_samples(
    samples: Iterable[Iterable[Real]], *, step: dict,
) -> tuple[tuple[float, ...], ...]:
    """Transform [sample, feature] rows using one stored normalization step.

    Args:
        samples: Ordered numeric feature rows, matching input_spec.features.
        step: A normalize step from ModelVersion.preprocessing, containing the
            method and fitted parameters from external training.

    Returns:
        Immutable float rows with the same sample and feature order. Empty input
        returns an empty tuple after validating the step. No input is modified.

    Raises:
        ValueError: If the step or samples are invalid, feature counts disagree,
            or a calculation produces a non-finite value, even before clipping.

    Standardization uses (x - mean) / scale. Min-max uses x * scale + offset,
    optionally clipped to the stored range. The none method preserves values.
    Parameters are never fitted or inferred from these samples.
    """
    validate_normalization(step)
    matrix = snapshot_samples(samples)
    method = step["method"]
    if method == "none":
        return matrix

    # Each fitted coefficient belongs to the feature at the same column index.
    if matrix and len(matrix[0]) != len(step["scale"]):
        raise ValueError("Normalization parameters must contain one value per input feature.")

    normalized = []
    for sample_index, row in enumerate(matrix):
        transformed_row = []
        for feature_index, value in enumerate(row):
            scale = step["scale"][feature_index]
            if method == "standardize":
                mean = step["mean"][feature_index]
                transformed = (value - mean) / scale
            else:
                offset = step["offset"][feature_index]
                transformed = value * scale + offset

            # Reject overflow rather than hiding it behind clipping.
            if not isfinite(transformed):
                raise ValueError(
                    f"Normalization produced a non-finite value at sample {sample_index}, feature {feature_index}."
                )
            if method == "minmax" and step["clip"]:
                lower, upper = step["range"]
                transformed = max(lower, min(upper, transformed))
            transformed_row.append(float(transformed))
        normalized.append(tuple(transformed_row))
    return tuple(normalized)
