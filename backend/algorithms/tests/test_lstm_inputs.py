from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

import numpy as np
import torch

from algorithms.preprocessing import iter_preprocessed_windows
from algorithms.runtimes.lstm_ae import LSTMArchitecture, LSTMAutoencoder


class LSTMInputTests(TestCase):
    def setUp(self):
        self.model = LSTMAutoencoder(LSTMArchitecture(2, 1, 0.2), ("pressure", "temperature"))

    def test_preprocessed_windows_become_a_batch_on_the_model_device(self):
        windows = list(iter_preprocessed_windows(
            [[10, 100], [20, 200], [30, 300]],
            preprocessing={"schema_version": 1, "steps": [{"type": "window", "size": 2, "tail": "reject"}]},
            input_spec={"features": list(self.model.features)},
            stride=1,
            offset=100,
        ))
        inputs = self.model.prepare_inputs([window.values for window in windows])
        self.assertEqual(tuple(inputs.shape), (2, 2, 2))
        self.assertEqual(inputs.device, self.model.device)
        self.assertEqual(inputs.dtype, next(self.model.parameters()).dtype)
        self.assertFalse(inputs.requires_grad)
        self.assertEqual(inputs.tolist(), [[[10, 100], [20, 200]], [[20, 200], [30, 300]]])
        self.assertEqual([(window.start, window.end) for window in windows], [(100, 102), (101, 103)])

    def test_device_is_taken_from_the_model_without_redetecting_hardware(self):
        # A CUDA-capable host may still run an explicitly CPU-placed model.
        with patch("algorithms.runtimes.torch_device.get_torch_device", side_effect=AssertionError("Redetected device")):
            inputs = self.model.prepare_inputs([[[1, 2]]])
        self.assertEqual(inputs.device, self.model.device)

    def test_lists_arrays_and_tensors_keep_values_and_feature_order(self):
        values = [[[1.25, 2.5], [3.75, 4.0]]]
        for data in (values, np.array(values, dtype=np.float64), torch.tensor(values, dtype=torch.float64)):
            with self.subTest(source=type(data)):
                inputs = self.model.prepare_inputs(data)
                self.assertEqual(inputs.tolist(), values)
                self.assertEqual(inputs.dtype, torch.float32)
                self.assertEqual(inputs.device, self.model.device)

    def test_input_dtype_follows_the_actual_model(self):
        self.model.to(dtype=torch.float64)
        values = [[[1.0000000001, 1e-100]]]
        inputs = self.model.prepare_inputs(values)
        self.assertEqual(inputs.dtype, torch.float64)
        self.assertEqual(inputs.tolist(), values)

    def test_input_data_and_training_graph_are_not_modified(self):
        values = [[[1.0, 2.0]]]
        original = deepcopy(values)
        self.model.prepare_inputs(values)
        self.assertEqual(values, original)
        source = torch.tensor(values, requires_grad=True)
        inputs = self.model.prepare_inputs(source)
        self.assertFalse(inputs.requires_grad)
        self.assertTrue(source.requires_grad)
        torch.testing.assert_close(inputs, source)

    def test_empty_wrong_rank_and_wrong_feature_count_are_rejected(self):
        for data in ([], [[]], [[[]]], [1, 2], [[1, 2]], [[[[1, 2]]]], [[[1]]], [[[1, 2, 3]]]):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "dimensions|feature count"):
                self.model.prepare_inputs(data)

    def test_invalid_shapes_fail_before_allocating_input_memory_on_the_model_device(self):
        with patch("algorithms.runtimes.lstm_ae.to_model_tensor") as transfer:
            with self.assertRaisesRegex(ValueError, "feature count"):
                self.model.prepare_inputs([[[1]]])
        transfer.assert_not_called()

    def test_ragged_non_numeric_boolean_complex_and_sparse_data_are_rejected(self):
        for data in (
            [[[1, 2], [3]]], [[["bad", 2]]], [[[True, False]]],
            torch.ones((1, 1, 2), dtype=torch.complex64), torch.ones((1, 1, 2)).to_sparse(),
        ):
            with self.subTest(source=type(data)), self.assertRaises(ValueError):
                self.model.prepare_inputs(data)

    def test_non_finite_values_and_float32_overflow_are_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), 1e300):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite"):
                self.model.prepare_inputs(torch.tensor([[[value, 2]]], dtype=torch.float64))

    def test_transfer_failure_is_reported_without_a_device_fallback(self):
        with (
            patch.object(torch.Tensor, "to", side_effect=RuntimeError("CUDA out of memory")) as transfer,
            self.assertRaisesRegex(ValueError, "Could not place input data.*out of memory"),
        ):
            self.model.prepare_inputs([[[1, 2]]])
        self.assertEqual(transfer.call_count, 1)
