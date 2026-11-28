"""Choose the loading function for each supported algorithm."""

from algorithms.runtimes.contracts import ModelLoader


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
