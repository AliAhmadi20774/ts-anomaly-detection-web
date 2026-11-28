"""Django adapters for the shared model metadata validation rules."""

import math

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

from algorithms._specs import (
    validate_input_spec,
    validate_json_object,
    validate_preprocessing,
    validate_preprocessing_input,
)


@deconstructible
class JsonObjectValidator:
    def __call__(self, value):
        try:
            validate_json_object(value)
        except ValueError as error:
            raise ValidationError(str(error)) from error


@deconstructible
class InputSpecValidator:
    """Preserve the ordered input features and optional expected sampling rate."""

    def __call__(self, value):
        try:
            validate_input_spec(value)
        except ValueError as error:
            raise ValidationError(str(error)) from error


@deconstructible
class PreprocessingValidator:
    """Validate a versioned declaration, without fitting or executing transforms."""

    def __call__(self, value):
        try:
            validate_preprocessing(value)
        except ValueError as error:
            raise ValidationError(str(error)) from error

    def validate_input(self, value, input_spec):
        """Cross-check fitted feature vectors and the single source of sample rate."""
        try:
            validate_preprocessing_input(value, input_spec)
        except ValueError as error:
            raise ValidationError(str(error)) from error


@deconstructible
class NonNegativeFiniteValidator:
    """Reject negative thresholds and non-finite floating-point values."""

    def __call__(self, value):
        try:
            valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValidationError("Use a finite, non-negative number.")
