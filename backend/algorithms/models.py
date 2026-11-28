from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models.lookups import Exact

from algorithms.runtimes.registry import validate_inference_params
from algorithms.validators import (
    InputSpecValidator, JsonObjectValidator, NonNegativeFiniteValidator, PreprocessingValidator,
)


class Algorithm(models.Model):
    """Identify an algorithm family independently of its trained model versions."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    key = models.CharField(
        max_length=64,
        unique=True,
        validators=[RegexValidator(
            r"\A[a-z][a-z0-9_]*\Z",
            "Use lowercase letters, digits and underscores, starting with a letter.",
        )],
    )
    name = models.CharField(
        max_length=160,
        validators=[RegexValidator(r"\S", "Name must contain a non-whitespace character.")],
    )

    class Meta:
        db_table = "algorithms"
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(key__regex=r"\A[a-z][a-z0-9_]*\Z"),
                name="algorithms_key_format",
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=r"\S"),
                name="algorithms_name_not_blank",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ModelArtifact(models.Model):
    """Track a private stored weights file independently of model metadata."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    file = models.FileField(max_length=255, unique=True)
    size_bytes = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        db_table = "model_artifacts"
        constraints = [
            models.CheckConstraint(condition=models.Q(size_bytes__gt=0), name="model_artifacts_size_positive"),
            models.CheckConstraint(condition=models.Q(file__regex=r"\S"), name="model_artifacts_file_not_blank"),
        ]

    def __str__(self) -> str:
        return self.file.name


class ModelVersion(models.Model):
    """Describe one trained model version without coupling columns to its architecture."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    algorithm = models.ForeignKey(Algorithm, on_delete=models.PROTECT, related_name="model_versions")
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    architecture_params = models.JSONField(default=dict, blank=True, validators=[JsonObjectValidator()])
    input_spec = models.JSONField(validators=[InputSpecValidator()])
    preprocessing = models.JSONField(default=None, null=True, blank=True, validators=[PreprocessingValidator()])
    weights = models.ForeignKey(
        ModelArtifact, on_delete=models.PROTECT, null=True, blank=True, related_name="model_versions",
    )

    class Meta:
        db_table = "model_versions"
        ordering = ["algorithm", "version"]
        constraints = [
            models.UniqueConstraint(fields=["algorithm", "version"], name="model_versions_algorithm_version_unique"),
            models.CheckConstraint(condition=models.Q(version__gt=0), name="model_versions_version_positive"),
            models.CheckConstraint(
                condition=Exact(
                    models.Func("architecture_params", function="jsonb_typeof", output_field=models.CharField()),
                    models.Value("object"),
                ),
                name="model_versions_architecture_object",
            ),
            models.CheckConstraint(
                condition=Exact(
                    models.Func("input_spec", function="jsonb_typeof", output_field=models.CharField()),
                    models.Value("object"),
                ),
                name="model_versions_input_object",
            ),
            models.CheckConstraint(
                condition=models.Q(preprocessing__isnull=True) | Exact(
                    models.Func("preprocessing", function="jsonb_typeof", output_field=models.CharField()),
                    models.Value("object"),
                ),
                name="model_versions_preprocessing_object",
            ),
        ]

    def clean(self):
        super().clean()
        # Allow an empty object, while rejecting empty non-object values that
        # Django skips during field validation when blank=True.
        try:
            JsonObjectValidator()(self.architecture_params)
        except ValidationError as error:
            raise ValidationError({"architecture_params": error.messages}) from error
        try:
            validator = PreprocessingValidator()
            # Validate empty non-None values too: blank=True skips field validation.
            validator(self.preprocessing)
            validator.validate_input(self.preprocessing, self.input_spec)
        except ValidationError as error:
            raise ValidationError({"preprocessing": error.messages}) from error

    def __str__(self) -> str:
        return f"{self.algorithm.key} v{self.version}"


class TestSection(models.Model):
    """A reusable half-open interval in a test definition's original samples."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    test = models.ForeignKey("devices.TestDefinition", on_delete=models.PROTECT, related_name="analysis_sections")
    name = models.CharField(max_length=160, validators=[RegexValidator(r"\S", "Name must not be blank.")])
    position = models.PositiveIntegerField()
    start_sample = models.PositiveBigIntegerField()
    end_sample = models.PositiveBigIntegerField()

    class Meta:
        db_table = "test_sections"
        ordering = ["test_id", "position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["test", "name"], name="test_sections_name_unique"),
            models.UniqueConstraint(fields=["test", "position"], name="test_sections_position_unique"),
            models.CheckConstraint(condition=models.Q(name__regex=r"\S"), name="test_sections_name_not_blank"),
            models.CheckConstraint(condition=models.Q(end_sample__gt=models.F("start_sample")), name="test_sections_bounds"),
        ]

    def __str__(self) -> str:
        return self.name


class SectionModelConfig(models.Model):
    """Select a model and explicit decision/execution settings for one section.

    Separate named configurations can reuse a model on different input signals
    in the same section. Trained preprocessing remains on ModelVersion.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    section = models.ForeignKey(TestSection, on_delete=models.PROTECT, related_name="model_configs")
    name = models.CharField(max_length=160, validators=[RegexValidator(r"\S", "Name must not be blank.")])
    model_version = models.ForeignKey(ModelVersion, on_delete=models.PROTECT, related_name="section_configs")
    threshold = models.FloatField(validators=[NonNegativeFiniteValidator()])
    stride = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    batch_size = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    inference_params = models.JSONField(validators=[JsonObjectValidator()])

    class Meta:
        db_table = "section_model_configs"
        ordering = ["section_id", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["section", "name"], name="section_configs_name_unique"),
            models.CheckConstraint(condition=models.Q(name__regex=r"\S"), name="section_configs_name_not_blank"),
            models.CheckConstraint(condition=models.Q(threshold__gte=0, threshold__lt=float("inf")), name="section_configs_threshold_finite"),
            models.CheckConstraint(condition=models.Q(stride__gt=0), name="section_configs_stride_positive"),
            models.CheckConstraint(condition=models.Q(batch_size__gt=0), name="section_configs_batch_positive"),
            models.CheckConstraint(
                condition=Exact(
                    models.Func("inference_params", function="jsonb_typeof", output_field=models.CharField()),
                    models.Value("object"),
                ),
                name="section_configs_params_object",
            ),
        ]

    def clean(self):
        super().clean()
        if self.model_version_id:
            try:
                algorithm_key = self.model_version.algorithm.key
            except ObjectDoesNotExist:
                return  # Field validation reports missing foreign keys.
            try:
                validate_inference_params(algorithm_key, self.inference_params)
            except ValueError as error:
                raise ValidationError({"inference_params": str(error)}) from error

    def __str__(self) -> str:
        return self.name


class SectionModelInput(models.Model):
    """Bind one trained input feature to an explicit physical signal definition."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    config = models.ForeignKey(SectionModelConfig, on_delete=models.CASCADE, related_name="inputs")
    feature_name = models.CharField(max_length=160)
    signal = models.ForeignKey("devices.SignalDefinition", on_delete=models.PROTECT, related_name="model_inputs")

    class Meta:
        db_table = "section_model_inputs"
        ordering = ["feature_name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["config", "feature_name"], name="section_inputs_feature_unique"),
            models.CheckConstraint(condition=models.Q(feature_name__regex=r"\A\S(?:.*\S)?\Z"), name="section_inputs_feature_trimmed"),
        ]

    def clean(self):
        super().clean()
        if self.config_id:
            try:
                config = self.config
                signal = self.signal if self.signal_id else None
            except ObjectDoesNotExist:
                return  # Field validation reports missing foreign keys.
            InputSpecValidator()(config.model_version.input_spec)
            if self.feature_name not in config.model_version.input_spec["features"]:
                raise ValidationError({"feature_name": "Feature must appear in the model's input_spec.features."})
            if signal is not None and signal.test_id != config.section.test_id:
                raise ValidationError({"signal": "Signal must belong to the section's test definition."})

    def __str__(self) -> str:
        return self.feature_name
