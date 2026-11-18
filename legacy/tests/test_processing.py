"""
Tests for signal processing module.
"""

import pytest
import numpy as np
import pandas as pd

from src.processing.signal import create_seq, regroup_multivariate_ts, preprocessing, preprocessing_with_bounds


class TestCreateSeq:
    """Tests for create_seq function."""
    
    def test_basic_sequence_creation(self):
        """Test basic sequence creation from DataFrame."""
        data = pd.DataFrame({
            0: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        })
        
        result = create_seq(data, step_window=2, size_window=4)
        
        assert result.shape[0] == 4  # (10 - 4) / 2 + 1 = 4 sequences
        assert result.shape[1] == 4  # window size
    
    def test_sequence_values(self):
        """Test that sequences contain correct values."""
        data = pd.DataFrame({
            0: [1, 2, 3, 4, 5, 6]
        })
        
        result = create_seq(data, step_window=1, size_window=3)
        
        assert np.array_equal(result[0], [1, 2, 3])
        assert np.array_equal(result[1], [2, 3, 4])
        assert np.array_equal(result[2], [3, 4, 5])
        assert np.array_equal(result[3], [4, 5, 6])


class TestRegroupMultivariateTS:
    """Tests for regroup_multivariate_ts function."""
    
    def test_combine_two_series(self):
        """Test combining two time series."""
        ts1 = np.random.rand(10, 5)
        ts2 = np.random.rand(10, 5)
        
        result = regroup_multivariate_ts([ts1, ts2])
        
        assert result.shape == (10, 5, 2)
    
    def test_single_series(self):
        """Test with single time series."""
        ts = np.random.rand(10, 5)
        
        result = regroup_multivariate_ts([ts])
        
        assert result.shape == (10, 5, 1)


class TestPreprocessing:
    """Tests for preprocessing function."""
    
    def test_mean_transformation(self):
        """Test preprocessing with mean transformation."""
        data = pd.DataFrame(np.random.rand(10, 100))
        
        result = preprocessing(data, ["mean"], "1", 10, 5)
        
        assert len(result.shape) == 3
        assert result.shape[2] == 1  # One feature (mean)
    
    def test_multiple_transformations(self):
        """Test preprocessing with multiple transformations."""
        data = pd.DataFrame(np.random.rand(10, 100))
        
        result = preprocessing(data, ["mean", "max", "min"], "1", 10, 5)
        
        assert len(result.shape) == 3
        assert result.shape[2] == 3  # Three features


class TestOriginalSampleBounds:
    @pytest.mark.parametrize("frequency, expected", [
        ("1", [[0, 2], [1, 3], [2, 4], [3, 5], [4, 6], [5, 7], [6, 8], [7, 9], [8, 10], [9, 11]]),
        ("2", [[0, 4], [2, 6], [4, 8], [6, 10], [8, 11]]),
        ("2.5", [[0, 5], [3, 8], [5, 10], [8, 11]]),
        ("5", [[0, 10], [5, 11]]),
    ])
    def test_bin_bounds_include_only_original_samples(self, frequency, expected):
        data = pd.DataFrame([np.arange(11), np.arange(11) + 100])
        windows, bounds = preprocessing_with_bounds(data, ["mean"], frequency, 2, 1)

        assert bounds.tolist() == expected
        assert windows.shape == (2 * len(expected), 2, 1)
        np.testing.assert_allclose(windows[len(expected):], windows[:len(expected)] + 100)

    def test_features_and_windows_use_the_same_resampled_bins(self):
        windows, bounds = preprocessing_with_bounds(
            pd.DataFrame([np.arange(11)]), ["mean", "max", "min"], "2.5", 2, 1,
        )
        np.testing.assert_allclose(windows[0], [[1, 2, 0], [3.5, 4, 3]])
        assert bounds[0].tolist() == [0, 5]
        assert bounds[-1].tolist() == [8, 11]

    def test_no_complete_window_has_no_bounds(self):
        windows, bounds = preprocessing_with_bounds(pd.DataFrame([[1, 2, 3]]), ["mean"], "2", 5, 1)
        assert windows.shape == (0, 5, 1)
        assert bounds.shape == (0, 2)
