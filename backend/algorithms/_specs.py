"""Framework-independent validation for model input and preprocessing metadata."""

import json
import math

from algorithms.normalization import validate_normalization


def _require_fields(value: dict, expected: set[str]) -> None:
    if set(value) != expected:
        raise ValueError(f"Expected exactly these fields: {', '.join(sorted(expected))}.")


def validate_json_object(value) -> None:
    """Require a JSON object containing serializable, finite values."""
    if not isinstance(value, dict):
        raise ValueError("Use a JSON object.")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Use valid JSON values with finite numbers.") from error


def validate_input_spec(value: dict) -> None:
    """Validate ordered input feature names and an optional expected sample rate."""
    validate_json_object(value)
    if set(value) - {"features", "sample_rate_hz"}:
        raise ValueError("Supported input fields are features and sample_rate_hz.")
    features = value.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Provide a non-empty ordered list of input feature names.")
    if not all(isinstance(feature, str) and feature.strip() == feature and feature for feature in features):
        raise ValueError("Feature names must be non-empty strings without surrounding whitespace.")
    if len(features) != len(set(features)):
        raise ValueError("Input feature names must be unique.")
    if "sample_rate_hz" in value:
        rate = value["sample_rate_hz"]
        try:
            valid_rate = type(rate) in (int, float) and rate > 0 and math.isfinite(rate)
        except OverflowError:
            valid_rate = False
        if not valid_rate:
            raise ValueError("Sample rate must be a finite number greater than zero.")


def validate_preprocessing(value: dict | None) -> None:
    """Validate schema-1 steps; None remains valid for unconfigured metadata."""
    if value is None:
        return
    validate_json_object(value)
    _require_fields(value, {"schema_version", "steps"})
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Only preprocessing schema_version 1 is supported.")
    steps = value["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a non-empty ordered list.")
    window_seen = False
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("Each preprocessing step must be an object.")
        kind = step.get("type")
        if kind == "normalize":
            validate_normalization(step)
        elif kind == "resample":
            _require_fields(step, {"type", "method"})
            if step["method"] not in ("mean", "min", "max"):
                raise ValueError("Resampling method must be mean, min or max.")
            if window_seen:
                raise ValueError("Resampling must precede windowing.")
        elif kind == "window":
            _require_fields(step, {"type", "size", "tail"})
            if window_seen:
                raise ValueError("Only one windowing step is supported.")
            if type(step["size"]) is not int or step["size"] < 1:
                raise ValueError("Window size must be a positive integer.")
            if step["tail"] not in ("drop", "reject"):
                raise ValueError("Window tail policy must be drop or reject.")
            window_seen = True
        else:
            raise ValueError("Step type must be resample, normalize or window.")


def validate_preprocessing_input(value: dict | None, input_spec: dict) -> None:
    """Cross-check already validated preprocessing and input metadata."""
    if value is None or not isinstance(input_spec, dict):
        return
    features = input_spec.get("features")
    for step in value["steps"]:
        if step["type"] == "resample" and "sample_rate_hz" not in input_spec:
            raise ValueError("Resampling requires the target sample_rate_hz in input_spec.")
        if step["type"] == "normalize" and isinstance(features, list):
            for key in ("mean", "scale", "offset"):
                if key in step and len(step[key]) != len(features):
                    raise ValueError(f"{key} must contain one value per input feature, in feature order.")
