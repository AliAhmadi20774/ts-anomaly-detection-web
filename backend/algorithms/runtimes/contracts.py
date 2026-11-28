"""Framework-independent contracts for loaded models and their loaders."""

from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class ModelRuntime(Protocol):
    """Shared identity of a loaded model, independent of its implementation.

    This is the loading contract only. Inference operations and their outputs
    will be specified separately; this interface does not imply inference is
    available. Callers treat these properties as read-only metadata.
    """

    @property
    def algorithm_key(self) -> str: ...

    @property
    def features(self) -> tuple[str, ...]: ...


class ModelLoader(Protocol):
    """Build a runtime from validated version metadata and a weights stream.

    source is a seekable binary stream owned by the caller. Implementations
    validate their own architecture and checkpoint format, returning a runtime
    whose identity matches the selected algorithm and ordered input features.
    Invalid model metadata or weights should raise ValueError.
    """

    def __call__(
        self, source: BinaryIO, *, architecture_params: dict, input_spec: dict,
    ) -> ModelRuntime: ...
