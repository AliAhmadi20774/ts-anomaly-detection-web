from copy import deepcopy
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
import warnings

import torch

from algorithms.runtimes.lstm_ae import LSTMArchitecture, LSTMAutoencoder, load_lstm_ae


class UnsupportedMetadata:
    pass


class LSTMLoadingTests(TestCase):
    def setUp(self):
        self.params = {"hidden_size": 2, "num_layers": 1, "dropout": 0.2}
        self.spec = {"features": ["pressure", "temperature"], "sample_rate_hz": 1000}
        # A small, explicit two-feature checkpoint with distinct known weights.
        self.state = {
            "encoder.lstm.weight_ih_l0": torch.full((8, 2), 0.1),
            "encoder.lstm.weight_hh_l0": torch.full((8, 2), 0.2),
            "encoder.lstm.bias_ih_l0": torch.full((8,), 0.3),
            "encoder.lstm.bias_hh_l0": torch.full((8,), 0.4),
            "decoder.lstm.weight_ih_l0": torch.full((8, 2), 0.5),
            "decoder.lstm.weight_hh_l0": torch.full((8, 2), 0.6),
            "decoder.lstm.bias_ih_l0": torch.full((8,), 0.7),
            "decoder.lstm.bias_hh_l0": torch.full((8,), 0.8),
            "decoder.linear.weight": torch.full((2, 2), 0.9),
            "decoder.linear.bias": torch.full((2,), 1.0),
        }

    def checkpoint(self, value):
        stream = BytesIO()
        torch.save(value, stream)
        stream.seek(0)
        return stream

    def load(self, value=None, **overrides):
        return load_lstm_ae(self.checkpoint(self.state if value is None else value), **{
            "architecture_params": self.params, "input_spec": self.spec, **overrides,
        })

    def test_plain_state_and_training_checkpoint_load_exact_weights(self):
        for checkpoint in (self.state, {"model_state_dict": self.state, "epoch": 4, "optimizer_state_dict": {"state": {}}}):
            with self.subTest(wrapped="model_state_dict" in checkpoint):
                model = self.load(checkpoint)
                self.assertEqual(model.features, ("pressure", "temperature"))
                for name, tensor in model.state_dict().items():
                    torch.testing.assert_close(tensor, self.state[name], rtol=0, atol=0)
                    self.assertEqual(tensor.device.type, "cpu")
                self.assertFalse(any(module.training for module in model.modules()))
                self.assertTrue(all(not parameter.requires_grad for parameter in model.parameters()))

    def test_layer_dimensions_and_feature_count_come_from_metadata(self):
        model = self.load()
        self.assertEqual(model.encoder.lstm.input_size, 2)
        self.assertEqual(model.encoder.lstm.hidden_size, 2)
        self.assertEqual(model.decoder.linear.out_features, 2)
        self.assertEqual(model.architecture.dropout, 0.2)
        self.assertEqual(model.encoder.lstm.dropout, 0)

    def test_stacked_layers_preserve_declared_dropout(self):
        architecture = LSTMArchitecture(hidden_size=3, num_layers=2, dropout=0.25)
        original = LSTMAutoencoder(architecture, ("pressure", "temperature"))
        model = self.load(original.state_dict(), architecture_params={"hidden_size": 3, "num_layers": 2, "dropout": 0.25})
        self.assertEqual(model.encoder.lstm.num_layers, 2)
        self.assertEqual(model.encoder.lstm.dropout, 0.25)
        torch.testing.assert_close(model.decoder.lstm.weight_ih_l1, original.decoder.lstm.weight_ih_l1)

    def test_single_layer_dropout_does_not_emit_a_warning(self):
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            self.load()
        self.assertEqual(emitted, [])

    def test_invalid_architecture_and_input_metadata_fail_before_deserialization(self):
        for params in (
            {}, {**self.params, "extra": 1}, {**self.params, "hidden_size": 0},
            {**self.params, "num_layers": True}, {**self.params, "hidden_size": "2"},
            {**self.params, "dropout": True}, {**self.params, "dropout": -0.1},
            {**self.params, "dropout": 1.1}, {**self.params, "dropout": float("nan")},
        ):
            with self.subTest(params=params), patch("algorithms.runtimes.lstm_ae.torch.load") as deserialize:
                with self.assertRaises(ValueError):
                    self.load(architecture_params=params)
                deserialize.assert_not_called()
        with self.assertRaises(ValueError):
            self.load(input_spec={"features": ["pressure", "pressure"]})

    def test_mismatched_features_hidden_size_and_layers_are_rejected_before_model_allocation(self):
        for options in (
            {"input_spec": {"features": ["pressure"]}},
            {"architecture_params": {**self.params, "hidden_size": 300}},
            {"architecture_params": {**self.params, "num_layers": 2}},
            {"architecture_params": {**self.params, "hidden_size": 10 ** 100}},
        ):
            with self.subTest(options=options), patch("algorithms.runtimes.lstm_ae.LSTMAutoencoder") as construct:
                with self.assertRaises(ValueError):
                    self.load(**options)
                construct.assert_not_called()

    def test_missing_unexpected_and_renamed_parameter_keys_are_rejected(self):
        missing = dict(self.state)
        missing.pop("decoder.linear.bias")
        renamed = dict(self.state)
        renamed["wrong.bias"] = renamed.pop("decoder.linear.bias")
        for state in (missing, {**self.state, "unexpected": torch.zeros(1)}, renamed):
            with self.subTest(keys=list(state)), self.assertRaisesRegex(ValueError, "keys"):
                self.load(state)

    def test_wrong_shapes_types_dtypes_and_non_finite_weights_are_rejected(self):
        for tensor in (
            torch.zeros(3), [1, 2], torch.ones(2, dtype=torch.int64), torch.ones(2, dtype=torch.float64),
            torch.tensor([float("nan"), 0]), torch.tensor([0, float("inf")]), torch.ones(2).to_sparse(),
            torch.empty(2, device="meta"),
        ):
            with self.subTest(tensor=tensor), self.assertRaises(ValueError):
                self.load({**self.state, "decoder.linear.bias": tensor})

    def test_corrupt_or_non_state_payloads_are_rejected(self):
        for data in (b"", b"not a checkpoint", self.checkpoint(self.state).getvalue()[:100]):
            with self.subTest(length=len(data)), self.assertRaisesRegex(ValueError, "checkpoint"):
                load_lstm_ae(BytesIO(data), architecture_params=self.params, input_spec=self.spec)
        for value in ([], {"model_state_dict": None}, {"model_state_dict": []}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load(value)

    def test_custom_serialized_objects_are_rejected_without_unrestricted_fallback(self):
        checkpoint = {"model_state_dict": self.state, "custom_metadata": UnsupportedMetadata()}
        with patch("algorithms.runtimes.lstm_ae.torch.load", wraps=torch.load) as deserialize:
            with self.assertRaisesRegex(ValueError, "supported tensor checkpoint"):
                self.load(checkpoint)
        self.assertEqual(deserialize.call_count, 1)
        self.assertEqual(deserialize.call_args.kwargs, {"map_location": "cpu", "weights_only": True})

    def test_loading_preserves_metadata_source_bytes_and_cpu_random_state(self):
        params, spec = deepcopy(self.params), deepcopy(self.spec)
        stream = self.checkpoint(self.state)
        content = stream.getvalue()
        random_state = torch.random.get_rng_state().clone()
        load_lstm_ae(stream, architecture_params=self.params, input_spec=self.spec)
        torch.testing.assert_close(torch.random.get_rng_state(), random_state, rtol=0, atol=0)
        self.assertEqual(self.params, params)
        self.assertEqual(self.spec, spec)
        self.assertEqual(stream.getvalue(), content)

    def test_explicit_cpu_float32_is_preserved_when_default_dtype_differs(self):
        original = torch.get_default_dtype()
        try:
            torch.set_default_dtype(torch.float64)
            model = self.load()
        finally:
            torch.set_default_dtype(original)
        self.assertTrue(all(parameter.dtype == torch.float32 for parameter in model.parameters()))

    def test_reconstruction_policy_is_not_silently_chosen_by_the_loader(self):
        with self.assertRaisesRegex(NotImplementedError, "Reconstruction"):
            self.load()(torch.zeros(1, 4, 2))
