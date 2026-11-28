"""The common interface used by every algorithm's loading function."""

from typing import TYPE_CHECKING, BinaryIO, Protocol, runtime_checkable

if TYPE_CHECKING:
    from algorithms.runtimes.torch_inference import ReconstructionResult


@runtime_checkable
class ModelRuntime(Protocol):
    """Metadata every loaded model must expose, regardless of its framework.

    Protocol describes the required attributes; models need not inherit from it.
    This interface covers loading only. It does not define inference yet.
    """

    @property
    def algorithm_key(self) -> str:
        """Algorithm identifier, such as 'lstm_ae'."""
        ...

    @property
    def features(self) -> tuple[str, ...]:
        """Input signal names in the exact order expected by the model."""
        ...


class ModelLoader(Protocol):
    """Signature shared by load_lstm_ae and future algorithm loaders."""

    def __call__(
        self,
        source: BinaryIO,
        *,
        architecture_params: dict,
        input_spec: dict,
    ) -> ModelRuntime:
        """Read weights and return a model; invalid metadata or weights raise ValueError.

        source is a seekable binary stream. The caller owns and closes it.
        Each loader validates its own architecture and checkpoint format.
        """
        ...


@runtime_checkable
class ReconstructionRuntime(ModelRuntime, Protocol):
    """Inference interface for runtimes returning reconstructions and window scores.

    This is separate from the loading contract: successfully loading another
    algorithm does not imply that it supports reconstruction-based inference.
    """

    def predict(self, data, *, reconstruction_repeats: int = 10) -> "ReconstructionResult":
        """Return one finite MSE score per input window on the runtime's device."""
        ...
