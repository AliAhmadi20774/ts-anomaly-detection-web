"""
Create .dat files using real Protocol Buffers (compatible with project's schema).
The output is gzip-compressed with .dat extension (matching project format).
"""

import gzip
import math
from typing import List

# Use the generated protobuf classes
import sys
sys.path.insert(0, '.')
from proto.generated.schema_pb2 import (
    Array_ProtoDevice,
    ProtoDevice,
    ProtoSignal,
    ProtoTestResult,
)


def create_sample_dat(
    output_path: str = "sample_signal.dat",
    device_series: str = "device1",
    serial_number: str = "SN001",
    test_name: str = "test2",
    signal_name: str = "signal1",
    signal_length: int = 22528
) -> str:
    """
    Create a .dat file with sample signal data using real protobuf serialization.
    The file is gzip-compressed but keeps .dat extension (matching project format).
    
    Args:
        output_path: Output path with .dat extension
        device_series: Device series name (must match project's CONFIG)
        serial_number: Serial number for the device
        test_name: Test name (must match project's CONFIG)
        signal_name: Name of the signal (typically "signal1")
        signal_length: Length of the signal array (22528 for device1)
    
    Returns:
        Path to the created .dat file
    """
    # Create the protobuf structure
    root = Array_ProtoDevice()
    
    # Set item details
    item = ProtoDevice()
    item.deviceSeries = device_series
    item.serialNumber = serial_number
    
    # Create test result
    test = ProtoTestResult()
    test.testName = test_name
    
    # Create signal with sample data (sine wave)
    signal = ProtoSignal()
    signal.name = signal_name
    
    # Generate sample signal data
    for i in range(signal_length):
        value = math.sin(2 * math.pi * i / 100) + (i / signal_length) * 0.5
        signal.data.append(value)
    
    # Build the hierarchy
    test.signals.append(signal)
    item.testResult.append(test)
    root.items.append(item)
    
    # Serialize using protobuf
    binary_data = root.SerializeToString()
    print(f"Protobuf serialized: {len(binary_data)} bytes")
    
    # Gzip compress and write to .dat file (project's format)
    with gzip.open(output_path, 'wb') as f:
        f.write(binary_data)
    
    print(f"Created: {output_path}")
    return output_path


def create_dat_from_signal(
    signal_data: List[float],
    output_path: str = "output.dat",
    device_series: str = "device1",
    serial_number: str = "SN001",
    test_name: str = "test2",
    signal_name: str = "signal1"
) -> str:
    """
    Create a .dat file from provided signal data using real protobuf.
    The file is gzip-compressed but keeps .dat extension (matching project format).
    
    Args:
        signal_data: List of float values for the signal
        output_path: Output path with .dat extension
        device_series: Device series name
        serial_number: Serial number
        test_name: Test name
        signal_name: Name of the signal
    
    Returns:
        Path to the created .dat file
    """
    # Create the protobuf structure
    root = Array_ProtoDevice()
    
    item = ProtoDevice()
    item.deviceSeries = device_series
    item.serialNumber = serial_number
    
    test = ProtoTestResult()
    test.testName = test_name
    
    signal = ProtoSignal()
    signal.name = signal_name
    signal.data.extend(signal_data)
    
    test.signals.append(signal)
    item.testResult.append(test)
    root.items.append(item)
    
    # Serialize
    binary_data = root.SerializeToString()
    print(f"Protobuf serialized: {len(binary_data)} bytes")
    
    # Gzip compress and write to .dat file
    with gzip.open(output_path, 'wb') as f:
        f.write(binary_data)
    
    print(f"Created: {output_path}")
    return output_path


if __name__ == "__main__":
    import random
    
    # Create sample .dat file with TWO tests: test1 and test2
    # test1: constant 0 with very small noise
    # test2: sine wave (original)
    
    signal_length = 22528
    
    # Create the protobuf structure
    root = Array_ProtoDevice()
    
    # Set item details
    item = ProtoDevice()
    item.deviceSeries = "device1"
    item.serialNumber = "SN001"
    
    # ========== TEST1: Constant 0 with very small noise ==========
    test1 = ProtoTestResult()
    test1.testName = "test1"
    
    signal1 = ProtoSignal()
    signal1.name = "signal1"
    # Generate constant 0 with very small noise (e.g., ±0.0001)
    for i in range(signal_length):
        value = random.uniform(-0.0001, 0.0001)
        signal1.data.append(value)
    
    test1.signals.append(signal1)
    item.testResult.append(test1)
    
    # ========== TEST2: Sine wave (original) ==========
    test2 = ProtoTestResult()
    test2.testName = "test2"
    
    signal2 = ProtoSignal()
    signal2.name = "signal1"
    # Generate sine wave
    for i in range(signal_length):
        value = math.sin(2 * math.pi * i / 100) + (i / signal_length) * 0.5
        signal2.data.append(value)
    
    test2.signals.append(signal2)
    item.testResult.append(test2)
    
    # Build the hierarchy
    root.items.append(item)
    
    # Serialize using protobuf
    binary_data = root.SerializeToString()
    print(f"Protobuf serialized: {len(binary_data)} bytes")
    
    # Gzip compress and write to .dat file
    output_path = "sample_signal.dat"
    with gzip.open(output_path, 'wb') as f:
        f.write(binary_data)
    
    print(f"Created: {output_path}")
    print(f"  - test1: constant 0 with small noise ({signal_length} points)")
    print(f"  - test2: sine wave ({signal_length} points)")
    print(f"\nDone!")
