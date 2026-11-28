"""Load a registered model using its metadata and private Django storage."""

from tempfile import SpooledTemporaryFile

from django.core.exceptions import ValidationError

from algorithms.models import ModelVersion
from algorithms.runtimes.contracts import ModelRuntime
from algorithms.runtimes.registry import LoaderRegistry, default_registry


def load_model_version(model_version_id, *, registry: LoaderRegistry | None = None) -> ModelRuntime:
    """Read a version and dispatch its weights to the selected algorithm loader.

    Files are opened through Django storage rather than an absolute local path,
    allowing the existing model mount or another configured storage backend.
    A seekable temporary snapshot is checked against the registered byte count
    before deserialization. Size is a consistency check, not a content hash.

    Unconfigured preprocessing does not block this weights-only check. It does
    not make that version ready for inference. Missing versions raise
    ModelVersion.DoesNotExist; invalid metadata or weights raise ValidationError.
    """
    version = ModelVersion.objects.select_related("algorithm", "weights").get(pk=model_version_id)
    version.full_clean()
    if registry is None:
        registry = default_registry
    try:
        loader = registry.get_loader(version.algorithm.key)
    except ValueError as error:
        raise ValidationError(str(error)) from error
    if version.weights_id is None:
        raise ValidationError("This model version has no registered weights.")
    expected_features = tuple(version.input_spec["features"])
    artifact = version.weights
    with SpooledTemporaryFile(max_size=16 * 1024 * 1024) as snapshot:
        try:
            with artifact.file.open("rb") as source:
                size = 0
                while chunk := source.read(64 * 1024):
                    size += len(chunk)
                    if size > artifact.size_bytes:
                        raise ValidationError("Weights file size differs from its registered size.")
                    snapshot.write(chunk)
        except OSError as error:
            raise ValidationError("Registered weights are unavailable. Check storage or restore the file.") from error
        if size != artifact.size_bytes:
            raise ValidationError("Weights file size differs from its registered size.")
        snapshot.seek(0)
        try:
            runtime = loader(snapshot, architecture_params=version.architecture_params, input_spec=version.input_spec)
        except ValueError as error:
            raise ValidationError(str(error)) from error
        # Structural protocol checks establish attribute presence, not values.
        # Verify identity here so a loader cannot silently return another model
        # family or reorder the input columns expected by the stored version.
        if not isinstance(runtime, ModelRuntime):
            raise ValidationError("The registered loader must return a ModelRuntime.")
        if runtime.algorithm_key != version.algorithm.key:
            raise ValidationError("Loaded runtime algorithm does not match the model version.")
        if runtime.features != expected_features:
            raise ValidationError("Loaded runtime features do not match input_spec.features in order.")
        return runtime
