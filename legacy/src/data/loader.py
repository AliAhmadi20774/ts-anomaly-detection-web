"""
Data loading module for compressed files.

This module handles loading and parallel processing of .dat.gz files.
Data is filtered by device and test name, and valid signals are extracted.

Functions:
    process_file_threaded: Process a single .dat file and extract signal
    load_valid_signals: Parallel loading of all files in directory with filtering
"""

import os
import gzip
import gc
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from tqdm import tqdm
from typing import List, Dict, Any, Optional, Tuple
from proto.generated.schema_pb2 import Array_ProtoDevice
from src.config.global_config import get_expected_signal_len

def process_file_threaded(
    file_path: str, 
    limited_tests: List[str], 
    device_series_available: List[str],
    report_callback: Optional[callable] = None,
    cancel_event: Optional[Any] = None
) -> Optional[Dict[str, Any]]:
    """
    File processing function for use with Threads.
    Parses a .dat file and extracts the signal if it matches the criteria.
    """
    if cancel_event and cancel_event.is_set():
        return None
        
    try:
        with gzip.open(file_path, "rb") as f:
            data = f.read()

        if cancel_event and cancel_event.is_set():
            return None

        root = Array_ProtoDevice()
        root.ParseFromString(data)
        if not root.items:
            return None

        item = root.items[0]

        device_series = item.deviceSeries
        if device_series not in device_series_available:
            return None

        serial_number = item.serialNumber.replace("/", "-")
        tests = item.testResult

        signal_list = None
        matched_test = None

        for test in tests:
            if test.testName in limited_tests:
                for signal in test.signals:
                    if signal.name in ("signal1", "Signal1"):
                        signal_list = list(signal.data)
                        matched_test = test.testName
                        break
                if signal_list is not None:
                    break

        if signal_list is not None and matched_test is not None:
            expected_len = get_expected_signal_len(device_series, matched_test)
            actual_len = len(signal_list)
            # Keep an empty signal distinguishable from measured zero values.
            # The runner retains its metadata for reports but never scores it.
            if 0 < actual_len < expected_len:
                signal_list = signal_list + [0.0] * (expected_len - actual_len)
            return {
                "signal_list": signal_list,
                "serial_number": serial_number,
                "signal_length": actual_len,
                "expected_length": expected_len,
                "length_matches_expected": actual_len == expected_len,
            }

        return None

    except Exception as e:
        if report_callback:
            report_callback(f"Error processing {file_path}: {e}")
        else:
            print(f"Error processing {file_path}: {e}")
        return None

def load_valid_signals(
    input_folder: str, 
    test_name: str, 
    device_series: str, 
    report_callback: Optional[callable] = None,
    cancel_event: Optional[Any] = None
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Orchestrates the loading of .dat files from a folder, filtering by test and device series.
    Returns a DataFrame of signals and a list of corresponding serial numbers.
    """
    max_workers = cpu_count()
    limited_tests = [test_name]
    device_series_available = [device_series]
    
    file_list = [
        os.path.join(input_folder, f) 
        for f in os.listdir(input_folder) 
        if f.lower().endswith(".dat")
    ]

    results_by_path = {}
    done = 0
    total_tasks = len(file_list)

    if report_callback:
        report_callback("========================\n")
        report_callback("Step 1/3: Loading data...\n")

    executor = ThreadPoolExecutor(max_workers=max_workers)
    cancelled_early = False
    future_to_file = {
        executor.submit(
            process_file_threaded,
            file_path,
            limited_tests,
            device_series_available,
            report_callback,
            cancel_event
        ): file_path
        for file_path in file_list
    }

    try:
        for future in tqdm(
            as_completed(future_to_file), total=total_tasks, desc="Loading files"
        ):
            if cancel_event and cancel_event.is_set():
                if report_callback:
                    report_callback("Cancel requested. Cancelling pending file loads...")
                for pending_future in future_to_file:
                    if not pending_future.done():
                        pending_future.cancel()
                cancelled_early = True
                executor.shutdown(wait=False, cancel_futures=True)
                raise InterruptedError("Loading cancelled")

            result = future.result()
            done += 1
            gc.collect()

            if report_callback:
                report_callback(f"Processing files: {done} / {total_tasks}")

            if result is not None:
                results_by_path[future_to_file[future]] = result
    finally:
        if not cancelled_early:
            executor.shutdown(wait=True, cancel_futures=False)

    df = pd.DataFrame(
        columns=[
            "signal",
            "serial_number",
            "signal_length",
            "expected_length",
            "length_matches_expected",
        ]
    )
    serial_numbers = []

    for file_path in file_list:
        result = results_by_path.get(file_path)
        if result is None:
            continue
        if cancel_event and cancel_event.is_set():
            break
        df.loc[len(df)] = [
            result["signal_list"],
            result["serial_number"],
            result["signal_length"],
            result["expected_length"],
            result["length_matches_expected"],
        ]
        serial_numbers.append(result["serial_number"])

    return df, serial_numbers
