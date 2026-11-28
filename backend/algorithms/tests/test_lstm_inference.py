from unittest import TestCase
from unittest.mock import patch

import torch

from algorithms.runtimes.lstm_ae import LSTMArchitecture, LSTMAutoencoder
from algorithms.runtimes.torch_inference import reconstruct_batch


class TorchTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        original_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        cls.addClassCleanup(torch.set_num_threads, original_threads)


class LSTMInferenceTests(TorchTestCase):
    def setUp(self):
        self.model = LSTMAutoencoder(LSTMArchitecture(2, 1, 0), ("pressure", "temperature")).eval()
        with torch.no_grad():
            for index, parameter in enumerate(self.model.parameters(), 1):
                parameter.fill_(index / 100)
        self.inputs = torch.tensor([[[1., 2.], [3., 4.], [5., 6.]], [[6., 5.], [4., 3.], [2., 1.]]])

    def test_forward_matches_recorded_reference_outputs(self):
        # Golden CPU outputs recorded from the previous model with these exact
        # weights, inputs and seed. No legacy project code is imported at runtime.
        expected = torch.tensor([
            [[0.1283658147, 0.1283658147], [0.1340661943, 0.1340661943], [0.1513281763, 0.1513281763]],
            [[0.1183127239, 0.1183127239], [0.1171662733, 0.1171662733], [0.1160208657, 0.1160208657]],
        ])
        with torch.random.fork_rng(devices=[]), torch.inference_mode():
            torch.manual_seed(123)
            actual = self.model(self.inputs)
        torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-7)

    def test_decoder_starts_at_last_sample_and_feeds_predictions_backwards(self):
        inputs = torch.tensor([[[0., 0.], [0., 0.], [10., 20.]]])
        states = (torch.zeros(1, 1, 2), torch.ones(1, 1, 2))

        def decode(values, hidden):
            return values + 1, hidden

        with (
            patch.object(self.model.encoder.lstm, "forward", return_value=(None, states)),
            patch.object(self.model.decoder.lstm, "forward", side_effect=decode) as decoder,
            patch.object(self.model.decoder.linear, "forward", side_effect=lambda values: values),
            torch.inference_mode(),
        ):
            actual = self.model(inputs)
        torch.testing.assert_close(actual, torch.tensor([[[13., 23.], [12., 22.], [11., 21.]]]))
        self.assertEqual(decoder.call_count, 3)
        self.assertIs(decoder.call_args_list[0].args[1], states)

    def test_stacked_layers_single_sample_and_multiple_features_keep_shape_and_dtype(self):
        model = LSTMAutoencoder(LSTMArchitecture(3, 2, 0.25), ("a", "b", "c")).double().eval()
        inputs = torch.ones((2, 1, 3), dtype=torch.float64)
        with torch.inference_mode():
            output = model(inputs)
        self.assertEqual(output.shape, inputs.shape)
        self.assertEqual(output.dtype, inputs.dtype)
        self.assertEqual(output.device, inputs.device)
        self.assertTrue(torch.isfinite(output).all().item())

    def test_eval_remains_stochastic_and_the_caller_can_reproduce_with_a_seed(self):
        with torch.random.fork_rng(devices=[]), torch.inference_mode():
            torch.manual_seed(123)
            first = self.model(self.inputs)
            second = self.model(self.inputs)
            torch.manual_seed(123)
            repeated = self.model(self.inputs)
        self.assertFalse(torch.equal(first, second))
        torch.testing.assert_close(first, repeated, rtol=0, atol=0)

    def test_predict_one_repeat_matches_one_forward_and_its_mse(self):
        with torch.random.fork_rng(devices=[]), torch.inference_mode():
            torch.manual_seed(123)
            expected = self.model(self.inputs)
            torch.manual_seed(123)
            result = self.model.predict(self.inputs.tolist(), reconstruction_repeats=1)
        torch.testing.assert_close(result.reconstruction, expected, rtol=0, atol=0)
        torch.testing.assert_close(result.scores, (self.inputs - expected).square().mean(dim=(1, 2)))
        self.assertEqual(result.reconstruction_repeats, 1)
        self.assertFalse(result.reconstruction.requires_grad)
        self.assertFalse(result.scores.requires_grad)

    def test_predict_respects_default_and_custom_repeat_counts_and_module_hooks(self):
        for count in (None, 1, 3):
            calls = []
            handle = self.model.register_forward_hook(lambda *_: calls.append(True))
            try:
                options = {} if count is None else {"reconstruction_repeats": count}
                result = self.model.predict(self.inputs, **options)
            finally:
                handle.remove()
            expected_count = 10 if count is None else count
            self.assertEqual(len(calls), expected_count)
            self.assertEqual(result.reconstruction_repeats, expected_count)

    def test_invalid_repeat_count_fails_before_preparing_data(self):
        for count in (0, -1, True, False, 1.5, "10", None):
            with (
                self.subTest(count=count),
                patch.object(self.model, "prepare_inputs") as prepare,
                self.assertRaisesRegex(ValueError, "reconstruction_repeats"),
            ):
                self.model.predict(self.inputs, reconstruction_repeats=count)
            prepare.assert_not_called()

    def test_prediction_disables_dropout_and_preserves_weights_and_input(self):
        self.model.train()
        original = {name: value.clone() for name, value in self.model.state_dict().items()}
        inputs = self.inputs.clone().requires_grad_(True)
        result = self.model.predict(inputs, reconstruction_repeats=2)
        self.assertFalse(any(module.training for module in self.model.modules()))
        self.assertTrue(inputs.requires_grad)
        torch.testing.assert_close(inputs, self.inputs, rtol=0, atol=0)
        for name, value in self.model.state_dict().items():
            torch.testing.assert_close(value, original[name], rtol=0, atol=0)
        self.assertFalse(result.reconstruction.requires_grad)

    def test_forward_rejects_unprepared_shapes_devices_and_dtypes(self):
        for inputs in (
            [[[1., 2.]]], torch.zeros(1, 3, 1), torch.empty(1, 0, 2),
            self.inputs.double(), self.inputs.to_sparse(), torch.empty((1, 3, 2), device="meta"),
        ):
            with self.subTest(source=type(inputs)), self.assertRaises(ValueError):
                self.model(inputs)


class ExampleAutoencoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1), requires_grad=False)
        self.calls = 0
        self.modes = []

    def forward(self, inputs):
        self.modes.append((self.training, torch.is_grad_enabled(), torch.is_inference_mode_enabled()))
        self.calls += 1
        return torch.full_like(inputs, 1 if self.calls == 1 else 3)


class ReconstructionScoringTests(TorchTestCase):
    def setUp(self):
        self.model = ExampleAutoencoder()
        self.inputs = torch.stack((torch.zeros(2, 2), torch.full((2, 2), 10.)))

    def test_average_precedes_mse_and_scores_reduce_samples_and_features_only(self):
        result = reconstruct_batch(self.model, self.inputs, reconstruction_repeats=2)
        torch.testing.assert_close(result.reconstruction, torch.full_like(self.inputs, 2))
        torch.testing.assert_close(result.scores, torch.tensor([4., 64.]))
        self.assertEqual(self.model.modes, [(False, False, True)] * 2)
        self.assertEqual(result.reconstruction_repeats, 2)

    def test_inference_does_not_mutate_a_model_output_that_aliases_its_input(self):
        original = self.inputs.clone()
        with patch.object(self.model, "forward", side_effect=lambda inputs: inputs):
            result = reconstruct_batch(self.model, self.inputs, reconstruction_repeats=2)
        torch.testing.assert_close(self.inputs, original, rtol=0, atol=0)
        torch.testing.assert_close(result.reconstruction, original, rtol=0, atol=0)
        torch.testing.assert_close(result.scores, torch.zeros(2), rtol=0, atol=0)

    def test_invalid_model_output_is_rejected(self):
        for output in (
            [], torch.zeros(1), self.inputs.double(), self.inputs.to_sparse(),
            torch.empty(self.inputs.shape, device="meta"),
            torch.full_like(self.inputs, float("nan")), torch.full_like(self.inputs, float("inf")),
        ):
            with (
                self.subTest(source=type(output)),
                patch.object(self.model, "forward", return_value=output),
                self.assertRaisesRegex(ValueError, "reconstruction"),
            ):
                reconstruct_batch(self.model, self.inputs, reconstruction_repeats=1)

    def test_invalid_inputs_are_rejected_before_the_model_runs(self):
        for inputs in (
            [], torch.empty(0, 2, 2), self.inputs.double(), self.inputs.to_sparse(),
            torch.empty(self.inputs.shape, device="meta"), torch.full_like(self.inputs, float("nan")),
        ):
            with self.subTest(source=type(inputs)), self.assertRaises(ValueError):
                reconstruct_batch(self.model, inputs)
        self.assertEqual(self.model.calls, 0)

    def test_mse_overflow_is_reported_instead_of_returning_infinite_scores(self):
        with (
            patch.object(self.model, "forward", return_value=torch.zeros_like(self.inputs)),
            self.assertRaisesRegex(ValueError, "MSE is non-finite"),
        ):
            reconstruct_batch(self.model, torch.full_like(self.inputs, 1e30), reconstruction_repeats=1)
