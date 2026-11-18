"""
Tests for model inference module.
"""

import pytest
import torch
from torch.utils.data import DataLoader

from src.inference.model_inference import get_avg_pred, get_original_ts
from src.models.lstm_autoencoder import LSTMAutoEncoder


class TestGetAvgPred:
    """Tests for get_avg_pred function."""
    
    def test_basic_inference(self):
        """Test basic model inference."""
        device = torch.device("cpu")
        
        model = LSTMAutoEncoder(
            num_layers=1,
            hidden_size=10,
            nb_feature=1,
            device=device
        )
        
        data = torch.randn(20, 50, 1)
        loader = DataLoader(data, batch_size=5, shuffle=False)
        
        predict, errors = get_avg_pred(
            loader, data, model, seq_length=50, device=device, epoch=2
        )
        
        assert predict.shape == data.shape
        assert len(errors) == 20
    
    def test_deterministic_output(self):
        """Test that multiple runs give same result with fixed seed."""
        device = torch.device("cpu")
        torch.manual_seed(42)
        
        model = LSTMAutoEncoder(
            num_layers=1,
            hidden_size=10,
            nb_feature=1,
            device=device
        )
        
        data = torch.randn(10, 30, 1)
        loader = DataLoader(data, batch_size=2, shuffle=False)
        
        predict1, errors1 = get_avg_pred(
            loader, data, model, seq_length=30, device=device, epoch=5
        )
        
        torch.manual_seed(42)
        model2 = LSTMAutoEncoder(
            num_layers=1,
            hidden_size=10,
            nb_feature=1,
            device=device
        )
        
        predict2, errors2 = get_avg_pred(
            loader, data, model2, seq_length=30, device=device, epoch=5
        )
        
        assert torch.allclose(predict1, predict2, rtol=1e-5)


class TestGetOriginalTs:
    """Tests for get_original_ts function."""
    
    def test_reconstruct_sequence(self):
        """Test reconstructing original time series."""
        data = torch.randn(12, 10, 1)  # 12 windows, 10 timesteps, 1 feature
        nb_ts_origine = 3
        size_window = 10
        step_window = 5
        nb_feature = 1
        
        result = get_original_ts(data, size_window, step_window, nb_ts_origine, nb_feature)
        
        expected_length = (size_window - step_window) + (10 - (size_window - step_window))
        assert result.shape[0] == nb_ts_origine
        assert result.shape[2] == nb_feature
    
    def test_overlap_handling(self):
        """Test that overlapping windows are handled correctly."""
        data = torch.ones(8, 4, 1)
        nb_ts_origine = 2
        size_window = 4
        step_window = 2
        nb_feature = 1
        
        result = get_original_ts(data, size_window, step_window, nb_ts_origine, nb_feature)
        
        assert result.shape[0] == 2
