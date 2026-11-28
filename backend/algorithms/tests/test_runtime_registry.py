from dataclasses import dataclass
import subprocess
import sys
from unittest import TestCase

from algorithms.runtimes.contracts import ModelRuntime
from algorithms.runtimes.registry import get_model_loader, validate_inference_params


@dataclass(frozen=True)
class ExampleRuntime:
    algorithm_key: str
    features: tuple[str, ...]


class RuntimeRegistryTests(TestCase):
    def test_lstm_resolves_directly_to_its_loading_function(self):
        from algorithms.runtimes.lstm_ae import load_lstm_ae

        self.assertIs(get_model_loader("lstm_ae"), load_lstm_ae)

    def test_unsupported_algorithms_never_fall_back_to_lstm(self):
        for key in ("transad", "anomaly_transformer", "unknown", "LSTM_AE", ""):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "No model loader is available"):
                get_model_loader(key)

    def test_selecting_an_unsupported_algorithm_does_not_import_torch(self):
        # A fresh process also checks the module's initial import behavior.
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
from algorithms.runtimes.registry import get_model_loader
assert 'torch' not in sys.modules
try:
    get_model_loader('unknown')
except ValueError:
    pass
else:
    raise AssertionError('Unsupported algorithm was accepted')
assert 'torch' not in sys.modules
"""],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_common_interface_does_not_require_a_torch_model(self):
        self.assertIsInstance(ExampleRuntime("example", ("pressure",)), ModelRuntime)
        self.assertNotIsInstance(object(), ModelRuntime)

    def test_inference_settings_do_not_fall_back_for_unsupported_algorithms(self):
        for key in ("transad", "anomaly_transformer", "unknown"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "No inference settings validator"):
                validate_inference_params(key, {"reconstruction_repeats": 10})
