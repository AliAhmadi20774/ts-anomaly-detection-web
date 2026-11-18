"""
Tests for data loader module.
"""

import pytest
import os
import tempfile
import gzip
import time
from pathlib import Path

from src.data.loader import process_file_threaded, load_valid_signals
from proto.generated.schema_pb2 import (
    Array_ProtoDevice,
    ProtoDevice,
    ProtoSignal,
    ProtoTestResult,
)


def create_test_dat_file(path: str, device_series: str, serial_number: str, 
                         test_name: str, signal_length: int) -> None:
    """Helper to create a test .dat file."""
    root = Array_ProtoDevice()
    item = ProtoDevice()
    item.deviceSeries = device_series
    item.serialNumber = serial_number
    
    test = ProtoTestResult()
    test.testName = test_name
    
    signal = ProtoSignal()
    signal.name = "signal1"
    signal.data.extend([1.0] * signal_length)
    
    test.signals.append(signal)
    item.testResult.append(test)
    root.items.append(item)
    
    binary_data = root.SerializeToString()
    
    with gzip.open(path, 'wb') as f:
        f.write(binary_data)


class TestProcessFileThreaded:
    """Tests for process_file_threaded function."""

    def test_empty_signal_is_retained_without_zero_padding(self, tmp_path):
        dat_file = tmp_path / "empty.dat"
        create_test_dat_file(str(dat_file), "device1", "EMPTY", "test1", 0)

        result = process_file_threaded(str(dat_file), ["test1"], ["device1"])

        assert result is not None
        assert result["signal_list"] == []
        assert result["signal_length"] == 0
        assert result["expected_length"] == 22528
        assert result["length_matches_expected"] is False
    
    def test_valid_file_correct_device(self, tmp_path):
        """Test processing a valid file with matching device."""
        dat_file = tmp_path / "test.dat"
        create_test_dat_file(str(dat_file), "device1", "SN001", "test1", 22528)
        
        result = process_file_threaded(
            str(dat_file),
            ["test1"],
            ["device1"]
        )
        
        assert result is not None
        assert result["serial_number"] == "SN001"
        assert len(result["signal_list"]) == 22528
    
    def test_wrong_device(self, tmp_path):
        """Test processing file with non-matching device."""
        dat_file = tmp_path / "test.dat"
        create_test_dat_file(str(dat_file), "device2", "SN001", "test1", 22528)
        
        result = process_file_threaded(
            str(dat_file),
            ["test1"],
            ["device1"]
        )
        
        assert result is None
    
    def test_wrong_signal_length(self, tmp_path):
        """Test processing file with incorrect signal length preserves warning metadata."""
        dat_file = tmp_path / "test.dat"
        create_test_dat_file(str(dat_file), "device1", "SN001", "test1", 1000)
        
        result = process_file_threaded(
            str(dat_file),
            ["test1"],
            ["device1"]
        )
        
        assert result is not None
        assert result["serial_number"] == "SN001"
        assert result["signal_length"] == 1000
        assert result["expected_length"] == 22528
        assert result["length_matches_expected"] is False
        assert len(result["signal_list"]) == 22528
        assert result["signal_list"][999] == 1.0
        assert result["signal_list"][1000] == 0.0

    def test_long_signal_is_not_truncated(self, tmp_path):
        """Test processing file with longer signal keeps original samples."""
        dat_file = tmp_path / "test_long.dat"
        create_test_dat_file(str(dat_file), "device1", "SN001", "test1", 23000)

        result = process_file_threaded(
            str(dat_file),
            ["test1"],
            ["device1"]
        )

        assert result is not None
        assert result["signal_length"] == 23000
        assert result["expected_length"] == 22528
        assert result["length_matches_expected"] is False
        assert len(result["signal_list"]) == 23000


class TestLoadValidSignals:
    """Tests for load_valid_signals function."""
    
    def test_load_multiple_files(self, tmp_path):
        """Test loading multiple valid files."""
        for i in range(3):
            dat_file = tmp_path / f"sample_{i:03d}.dat"
            create_test_dat_file(str(dat_file), "device1", f"SN{i:03d}", "test1", 22528)
        
        df, serials = load_valid_signals(
            str(tmp_path),
            "test1",
            "device1"
        )
        
        assert len(df) == 3
        assert len(serials) == 3
        assert all(len(s) == 22528 for s in df["signal"])
    
    def test_empty_folder(self, tmp_path):
        """Test loading from empty folder."""
        df, serials = load_valid_signals(
            str(tmp_path),
            "test1",
            "device1"
        )
        
        assert len(df) == 0
        assert len(serials) == 0

    def test_load_preserves_input_file_order(self, tmp_path, monkeypatch):
        """Loaded rows should follow input file order, not thread completion order."""
        file_specs = [
            ("sample_000.dat", "SN000", 0.15),
            ("sample_001.dat", "SN001", 0.05),
            ("sample_002.dat", "SN002", 0.0),
        ]
        for file_name, serial, _delay in file_specs:
            dat_file = tmp_path / file_name
            create_test_dat_file(str(dat_file), "device1", serial, "test1", 22528)

        original = process_file_threaded
        delays = {str(tmp_path / file_name): delay for file_name, _serial, delay in file_specs}

        def delayed_process(file_path, limited_tests, device_series_available, report_callback=None, cancel_event=None):
            time.sleep(delays[file_path])
            return original(file_path, limited_tests, device_series_available, report_callback, cancel_event)

        monkeypatch.setattr("src.data.loader.process_file_threaded", delayed_process)

        df, serials = load_valid_signals(
            str(tmp_path),
            "test1",
            "device1"
        )

        assert list(df["serial_number"]) == ["SN000", "SN001", "SN002"]
        assert serials == ["SN000", "SN001", "SN002"]
