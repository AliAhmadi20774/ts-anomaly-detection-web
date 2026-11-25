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
