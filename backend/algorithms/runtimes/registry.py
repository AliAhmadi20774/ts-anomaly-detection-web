"""Select an explicitly registered model loader by algorithm key."""

import re
from typing import BinaryIO

from algorithms.runtimes.contracts import ModelLoader, ModelRuntime


class LoaderRegistry:
    """Keep one loader per algorithm without importing code from database values."""

    def __init__(self):
        self._loaders: dict[str, ModelLoader] = {}

    def register(self, algorithm_key: str, loader: ModelLoader) -> None:
        """Register a loader explicitly; reject invalid keys and replacements."""
        if not isinstance(algorithm_key, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", algorithm_key) is None:
            raise ValueError("Algorithm key must use lowercase letters, digits and underscores, starting with a letter.")
        if not callable(loader):
            raise ValueError("A model loader must be callable.")
        if algorithm_key in self._loaders:
            raise ValueError(f"A model loader is already registered for algorithm '{algorithm_key}'.")
        self._loaders[algorithm_key] = loader

    def get_loader(self, algorithm_key: str) -> ModelLoader:
        """Resolve a supported algorithm; unknown algorithms have no fallback."""
        try:
            return self._loaders[algorithm_key]
        except KeyError as error:
            raise ValueError(f"No model loader is registered for algorithm '{algorithm_key}'.") from error


def _load_lstm_ae(source: BinaryIO, *, architecture_params: dict, input_spec: dict) -> ModelRuntime:
    # Import the framework only when this particular algorithm is selected.
    from algorithms.runtimes.lstm_ae import load_lstm_ae

    return load_lstm_ae(source, architecture_params=architecture_params, input_spec=input_spec)


default_registry = LoaderRegistry()
default_registry.register("lstm_ae", _load_lstm_ae)
