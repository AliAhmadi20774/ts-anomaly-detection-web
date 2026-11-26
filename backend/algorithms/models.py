from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models.lookups import Exact

from algorithms.validators import InputSpecValidator, JsonObjectValidator


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
        ]

    def clean(self):
        super().clean()
        # Allow an empty object, while rejecting empty non-object values that
        # Django skips during field validation when blank=True.
        try:
            JsonObjectValidator()(self.architecture_params)
        except ValidationError as error:
            raise ValidationError({"architecture_params": error.messages}) from error

    def __str__(self) -> str:
        return f"{self.algorithm.key} v{self.version}"
