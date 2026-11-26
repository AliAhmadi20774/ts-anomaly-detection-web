import json
import math

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class JsonObjectValidator:
    def __call__(self, value):
        if not isinstance(value, dict):
            raise ValidationError("Use a JSON object.")
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValidationError("Use valid JSON values with finite numbers.") from error


@deconstructible
class InputSpecValidator:
    """Preserve the ordered input features and optional expected sampling rate."""

    def __call__(self, value):
        JsonObjectValidator()(value)
        if set(value) - {"features", "sample_rate_hz"}:
            raise ValidationError("Supported input fields are features and sample_rate_hz.")
        features = value.get("features")
        if not isinstance(features, list) or not features:
            raise ValidationError("Provide a non-empty ordered list of input feature names.")
        if not all(isinstance(feature, str) and feature.strip() == feature and feature for feature in features):
            raise ValidationError("Feature names must be non-empty strings without surrounding whitespace.")
        if len(features) != len(set(features)):
            raise ValidationError("Input feature names must be unique.")
        if "sample_rate_hz" in value:
            rate = value["sample_rate_hz"]
            try:
                valid_rate = type(rate) in (int, float) and rate > 0 and math.isfinite(rate)
            except OverflowError:
                valid_rate = False
            if not valid_rate:
                raise ValidationError("Sample rate must be a finite number greater than zero.")


@deconstructible
class PreprocessingValidator:
    """Validate a versioned declaration, without fitting or executing transforms."""

    @staticmethod
    def _fields(value, expected):
        if set(value) != set(expected):
            raise ValidationError(f"Expected exactly these fields: {', '.join(sorted(expected))}.")

    @staticmethod
    def _finite(value):
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            return False

    def _vector(self, value, name, *, positive=False):
        if not isinstance(value, list) or not value:
            raise ValidationError(f"{name} must be a non-empty numeric list in input feature order.")
        if not all(self._finite(item) and (not positive or item > 0) for item in value):
            raise ValidationError(f"{name} must contain finite {'positive ' if positive else ''}numbers.")

    def _normalization(self, step):
        method = step.get("method")
        if method == "none":
            self._fields(step, {"type", "method"})
        elif method == "standardize":
            self._fields(step, {"type", "method", "mean", "scale"})
            self._vector(step["mean"], "mean")
            self._vector(step["scale"], "scale", positive=True)
            if len(step["mean"]) != len(step["scale"]):
                raise ValidationError("mean and scale must have the same length.")
        elif method == "minmax":
            self._fields(step, {"type", "method", "scale", "offset", "range", "clip"})
            self._vector(step["scale"], "scale")
            self._vector(step["offset"], "offset")
            self._vector(step["range"], "range")
            if len(step["scale"]) != len(step["offset"]) or any(scale < 0 for scale in step["scale"]):
                raise ValidationError("Min-max scale and offset must have equal lengths and scales must be non-negative.")
            bounds = step["range"]
            if len(bounds) != 2 or bounds[1] <= bounds[0] or not self._finite(bounds[1] - bounds[0]):
                raise ValidationError("range must contain an increasing pair with a finite positive span.")
            if type(step["clip"]) is not bool:
                raise ValidationError("clip must be true or false.")
        else:
            raise ValidationError("Normalization method must be none, standardize or minmax.")

    def __call__(self, value):
        if value is None:
            return
        JsonObjectValidator()(value)
        self._fields(value, {"schema_version", "steps"})
        if type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise ValidationError("Only preprocessing schema_version 1 is supported.")
        steps = value["steps"]
        if not isinstance(steps, list) or not steps:
            raise ValidationError("steps must be a non-empty ordered list.")
        window_seen = False
        for step in steps:
            if not isinstance(step, dict):
                raise ValidationError("Each preprocessing step must be an object.")
            kind = step.get("type")
            if kind == "normalize":
                self._normalization(step)
            elif kind == "resample":
                self._fields(step, {"type", "method"})
                if step["method"] not in ("mean", "min", "max"):
                    raise ValidationError("Resampling method must be mean, min or max.")
                if window_seen:
                    raise ValidationError("Resampling must precede windowing.")
            elif kind == "window":
                self._fields(step, {"type", "size", "tail"})
                if window_seen:
                    raise ValidationError("Only one windowing step is supported.")
                if type(step["size"]) is not int or step["size"] < 1:
                    raise ValidationError("Window size must be a positive integer.")
                if step["tail"] not in ("drop", "reject"):
                    raise ValidationError("Window tail policy must be drop or reject.")
                window_seen = True
            else:
                raise ValidationError("Step type must be resample, normalize or window.")

    def validate_input(self, value, input_spec):
        """Cross-check fitted feature vectors and the single source of sample rate."""
        if value is None or not isinstance(input_spec, dict):
            return
        features = input_spec.get("features")
        for step in value["steps"]:
            if step["type"] == "resample" and "sample_rate_hz" not in input_spec:
                raise ValidationError("Resampling requires the target sample_rate_hz in input_spec.")
            if step["type"] == "normalize" and isinstance(features, list):
                for key in ("mean", "scale", "offset"):
                    if key in step and len(step[key]) != len(features):
                        raise ValidationError(f"{key} must contain one value per input feature, in feature order.")
