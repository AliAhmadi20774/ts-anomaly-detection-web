"""
Create a folder with 10 sample .dat files containing pseudo-sinusoidal signals.
"""

import os
import sys
import math
import gzip
sys.path.insert(0, '.')
from proto.generated.schema_pb2 import (
    Array_ProtoDevice,
    ProtoDevice,
    ProtoSignal,
    ProtoTestResult,
)


def create_dat_file(output_path: str, device_series: str, serial_number: str,
                    test1_data: list, test2_data: list) -> None:
    """Create a gzip-compressed .dat file with protobuf structure containing both test1 and test2."""
    root = Array_ProtoDevice()
    
    item = ProtoDevice()
    item.deviceSeries = device_series
    item.serialNumber = serial_number
    
    # ========== TEST1: Constant 0 with very small noise ==========
    test1 = ProtoTestResult()
    test1.testName = "test1"
    
    signal1 = ProtoSignal()
    signal1.name = "signal1"
    signal1.data.extend(test1_data)
    
    test1.signals.append(signal1)
    item.testResult.append(test1)
    
    # ========== TEST2: Custom signal data ==========
    test2 = ProtoTestResult()
    test2.testName = "test2"
    
    signal2 = ProtoSignal()
    signal2.name = "signal1"
    signal2.data.extend(test2_data)
    
    test2.signals.append(signal2)
    item.testResult.append(test2)
    
    # Build the hierarchy
    root.items.append(item)
    
    binary_data = root.SerializeToString()
    
    with gzip.open(output_path, 'wb') as f:
        f.write(binary_data)
    
    print(f"  Created: {os.path.basename(output_path)} (test1 + test2)")


def generate_pseudo_sinusoidal_signal(length: int, frequency: float, 
                                       noise_level: float = 0.1) -> list:
    """
    Generate a pseudo-sinusoidal signal with some noise.
    
    Args:
        length: Signal length (number of samples)
        frequency: Frequency of the sine wave
        noise_level: Amount of random noise to add
    
    Returns:
        List of float values
    """
    import random
    signal = []
    for i in range(length):
        # Base sine wave
        value = math.sin(2 * math.pi * frequency * i / 100)
        # Add amplitude modulation
        value *= (1 + 0.5 * math.sin(2 * math.pi * 0.01 * i))
        # Add noise
        value += random.gauss(0, noise_level)
        signal.append(value)
    return signal


def generate_constant_noise_signal(length: int, noise_level: float = 0.0001) -> list:
    """
    Generate a constant 0 signal with very small noise.
    
    Args:
        length: Signal length (number of samples)
        noise_level: Amount of random noise (default: ±0.0001)
    
    Returns:
        List of float values
    """
    import random
    signal = []
    for i in range(length):
        value = random.uniform(-noise_level, noise_level)
        signal.append(value)
    return signal


def main():
    # Create output folder
    output_folder = "sample_dat_files"
    os.makedirs(output_folder, exist_ok=True)
    
    # Parameters
    device_series = "device1"
    signal_length = 22528
    
    # Create 10 .dat files with both test1 and test2
    for i in range(1, 11):
        output_path = os.path.join(output_folder, f"sample_{i:03d}.dat")
        
        # TEST1: Constant 0 with very small noise (same for all files)
        test1_data = generate_constant_noise_signal(
            length=signal_length,
            noise_level=0.0001
        )
        
        # TEST2: Pseudo-sinusoidal signal with different frequency for each file
        frequency = 0.5 + i * 0.1  # Different frequency for each file
        noise_level = 0.05 + i * 0.01  # Slightly different noise
        
        test2_data = generate_pseudo_sinusoidal_signal(
            length=signal_length,
            frequency=frequency,
            noise_level=noise_level
        )
        
        serial_number = f"SN{i:03d}"
        
        create_dat_file(
            output_path=output_path,
            device_series=device_series,
            serial_number=serial_number,
            test1_data=test1_data,
            test2_data=test2_data
        )
    
    print(f"\nDone! Created 10 .dat files in '{output_folder}/' folder")
    print("  Each file contains:")
    print("    - test1: constant 0 with small noise")
    print("    - test2: pseudo-sinusoidal signal")


if __name__ == "__main__":
    main()
