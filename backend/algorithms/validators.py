"""Django adapters for the shared model metadata validation rules."""

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
