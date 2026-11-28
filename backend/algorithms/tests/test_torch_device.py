from unittest import TestCase
from unittest.mock import patch

import torch

from algorithms.runtimes.torch_device import get_torch_device


class TorchDeviceTests(TestCase):
    def test_cpu_is_selected_when_cuda_is_unavailable(self):
        with patch("algorithms.runtimes.torch_device.torch.cuda.is_available", return_value=False):
            self.assertEqual(get_torch_device(), torch.device("cpu"))

    def test_first_visible_cuda_device_is_preferred_when_available(self):
        with patch("algorithms.runtimes.torch_device.torch.cuda.is_available", return_value=True):
            self.assertEqual(get_torch_device(), torch.device("cuda:0"))
