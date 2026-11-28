"""Choose the loading function for each supported algorithm."""

from algorithms.runtimes.contracts import ModelLoader
from algorithms._specs import validate_json_object


def get_model_loader(algorithm_key: str) -> ModelLoader:
    """Return a loader without loading weights or running the model.

    Add one explicit case here when implementing another algorithm's loader.
    Imports stay inside their cases so unused frameworks are not loaded.
    """
    match algorithm_key:
        case "lstm_ae":
            from algorithms.runtimes.lstm_ae import load_lstm_ae

            return load_lstm_ae
        case _:
            raise ValueError(f"No model loader is available for algorithm '{algorithm_key}'.")


def validate_inference_params(algorithm_key: str, params: dict) -> None:
    """Validate explicit execution settings without importing a model framework."""
    validate_json_object(params)
    match algorithm_key:
        case "lstm_ae":
            if set(params) != {"reconstruction_repeats"}:
                raise ValueError("LSTM-AE inference_params must contain only reconstruction_repeats.")
            repeats = params["reconstruction_repeats"]
            if type(repeats) is not int or repeats < 1:
                raise ValueError("reconstruction_repeats must be a positive integer.")
        case _:
            raise ValueError(f"No inference settings validator is available for algorithm '{algorithm_key}'.")
