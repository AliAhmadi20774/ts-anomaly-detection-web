"""
Anomaly detection runner module for time series data.

This module executes the complete anomaly detection pipeline, including:
- Loading and preprocessing data
- Running LSTM Autoencoder model for anomaly scoring
- Generating plots and saving results

Functions:
    run_anomaly_detection: Main function that executes the full pipeline with progress reporting and cancellation support.
"""

from dataclasses import dataclass
from torch.utils.data import DataLoader
from typing import Callable, Optional, Tuple, List, Dict, Any
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
import threading
import pandas as pd
from src.data.loader import load_valid_signals
from src.processing.signal import preprocessing_with_bounds
from src.inference.model_inference import get_avg_pred
from src.visualization.plots import plot_anomaly
from src.visualization.html_report import (
    save_section_data,
    write_signal_inventory,
    generate_all_html_reports,
    generate_batch_html_reports,
    generate_run_dashboard,
    generate_batch_dashboard,
)
from src.visualization.pdf_report import (
    generate_all_pdf_reports,
    generate_batch_pdf_reports,
)
import numpy as np
import torch
from src.models.lstm_autoencoder import LSTMAutoEncoder
from src.data.airbus_dataset import AirbusData
from src.config import global_config as CFG
import gc

device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


def remove_duplicates_dict_list(dict_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate dictionaries while preserving first-seen order."""
    seen = set()
    unique_items = []
    for item in dict_list:
        marker = tuple(sorted(item.items()))
        if marker in seen:
            continue
        seen.add(marker)
        unique_items.append(item)
    return unique_items


def sort_errors_by_section_order(
    errors: List[Dict[str, Any]], sections_order: List[str]
) -> List[Dict[str, Any]]:
    """Sort errors by configured section order while preserving within-section order."""
    section_positions = {section: idx for idx, section in enumerate(sections_order)}
    fallback_index = len(section_positions)
    return sorted(
        errors,
        key=lambda error: section_positions.get(error.get("section"), fallback_index),
    )


@dataclass(frozen=True)
class UserConfig:
    folder: str
    device_series: str
    test_name: str
    create_plot: bool = False
    create_pdf: bool = False



def _create_output_structure(run_dir, section) -> Tuple[Path, Path, Path]:
    """
    Creates:
      base_dir/
        output_YYYYMMDD_HHMMSS/
          0/
          1/
    Returns: (run_dir, neg_dir, pos_dir)
    """
    sec_dir = run_dir / section
    neg_dir = sec_dir / "0"
    pos_dir = sec_dir / "1"

    neg_dir.mkdir(parents=True, exist_ok=False)
    pos_dir.mkdir(parents=True, exist_ok=False)

    return sec_dir, neg_dir, pos_dir


def run_anomaly_detection(
    config: UserConfig,
    report: Optional[Callable[[str], None]] = None,
    set_progress: Optional[Callable[[float], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    output_subdir: str = "single",
    batch_timestamp: Optional[str] = None,
    defer_html_outputs: bool = False,
    defer_pdf_outputs: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Anomaly detection pipeline with HTML reports and UI progress callbacks.
    - report(message): sends a text message
    - set_progress(value): sets progress in range [0.0, 1.0]
    - cancel_event: if set, stops the process early
    - output_subdir: "single" for single test, "batch/{device}" for batch runs
    - batch_timestamp: timestamp for batch runs (shared across all tests)

    Also creates an output folder (with timestamp) in the current working directory,
    containing subfolders 0 and 1 for negative/positive samples.
    """

    def _report(msg: str) -> None:
        if report:
            report(msg)

    def _progress(x: float) -> None:
        if set_progress:
            set_progress(max(0.0, min(1.0, x)))

    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    input_folder = config.folder

    _report("Step 1/3: Loading data...\n")
    df, serial_numbers = load_valid_signals(
        input_folder=input_folder,
        test_name=config.test_name,
        device_series=config.device_series,
        report_callback=_report,
        cancel_event=cancel_event
    )

    if _cancelled():
        _report("Loading cancelled.")
        _progress(0.0)
        return None

    base_dir = Path.cwd() / "outputs" / output_subdir
    base_dir.mkdir(exist_ok=True, parents=True)
    
    # Use provided timestamp for batch mode, or generate new one for single mode
    if batch_timestamp:
        timestamp = batch_timestamp
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if output_subdir.startswith("batch/"):
        # Batch mode: outputs/batch/{device}/{timestamp}/{test_name}/...
        device_part = output_subdir.replace("batch/", "")
        base_dir = Path.cwd() / "outputs" / "batch" / device_part / timestamp
        base_dir.mkdir(exist_ok=True, parents=True)
        run_dir = base_dir / f"{config.test_name}"
    else:
        # Single mode: outputs/single/{device}/{test_name}/{timestamp}/...
        run_dir = base_dir / f"{config.device_series}" / f"{config.test_name}" / f"{timestamp}"
    
    run_dir.mkdir(parents=True, exist_ok=True)

    signal_inventory = []
    for _, row in df.iterrows():
        signal_inventory.append(
            {
                "serial_number": str(row["serial_number"]),
                "signal_length": int(row["signal_length"]),
                "expected_length": int(row["expected_length"]),
                "length_matches_expected": bool(row["length_matches_expected"]),
            }
        )
    write_signal_inventory(run_dir / "reports", signal_inventory)

    # Preserve every loaded serial for reporting, including empty signals. Only
    # measured signals may enter section preprocessing or model inference.
    all_serial_numbers = [str(sn) for sn in serial_numbers]
    signal_map = {
        str(row["serial_number"]): row["signal"] for _, row in df.iterrows()
    }
    for _, row in df[df["signal_length"] == 0].iterrows():
        _report(f"No data for serial {row['serial_number']}, test {config.test_name}; model evaluation skipped.\n")
    df = df[df["signal_length"] > 0].reset_index(drop=True)
    serial_numbers = df["serial_number"].tolist()
    _report(f"\nNumber of signals to evaluate: {len(df)}\n")
    if not df.empty:
        _report(f"model loads on {device}.\n")

    _progress(0.33)
    errors = []

    sections = CFG.get_sections_order(config.device_series, config.test_name)
    if not sections:
        raise RuntimeError(f"No sections configured for {config.device_series}/{config.test_name}")


    base_prog = 0.33
    remaining = 1.0 - base_prog
    per_section = remaining / max(1, len(sections))


    for si, section in enumerate(sections if not df.empty else []):
        if _cancelled():
            _report("Cancel requested. Stopping...")
            break

        _report("\n========================\n")
        _report(f"SECTION: {section}\n")

        sec_params = CFG.get_section_params(config.device_series, config.test_name, section)

        # Slice data for section
        df_section = pd.DataFrame(columns=["signal"])
        df_section["signal"] = df["signal"].apply(lambda x: x[sec_params["start"]:sec_params["end"]])

        max_len = max(len(x) for x in df_section["signal"])
        time = np.arange(max_len) * 0.001
        test = pd.DataFrame(df_section["signal"].to_list(), columns=time)

        nb_ts_origine = len(df_section)
        del df_section

        batch_size = sec_params["batch_size"]
        step_window = sec_params["step_window"]
        size_window = sec_params["size_window"]

        # Preprocess
        test_seq, window_bounds = preprocessing_with_bounds(
            test,
            sec_params["transfo"],
            resample_freq=sec_params["resample_freq"],
            size_window=size_window,
            step_window=step_window,
        )

        test_seq = torch.from_numpy(test_seq).float()
        test_seq = AirbusData(test_seq)
        test_loader = DataLoader(test_seq, batch_size, shuffle=False)

        size_data, seq_length, nb_feature = test_seq.data.shape
        n_windows_per_ts = len(window_bounds)
        if size_data != nb_ts_origine * n_windows_per_ts:
            raise RuntimeError("Model windows do not match their original-sample bounds")

        # Load model
        model_best = LSTMAutoEncoder(
            num_layers=sec_params["num_layers"],
            hidden_size=sec_params["hidden_size"],
            nb_feature=1,
            dropout=sec_params.get("dropout", 0),
            device=device,
        ).to(device)

        checkpoint = torch.load(
            CFG.resource_path(sec_params["model_path"]),
            map_location=device,
        )
        model_best.load_state_dict(checkpoint["model_state_dict"])

        _report("Step 2/3: Scoring anomalies...\n")
        test_pred, test_errors = get_avg_pred(
            test_loader,
            test_seq.data,
            model_best,
            seq_length,
            device,
            cancel_fn=_cancelled,
        )

        # Output folders
        _report("Creating output folders...\n")
        sec_dir, neg_dir, pos_dir = _create_output_structure(run_dir, section)
        _report(f"Output:\n{run_dir}\n")
        _report(f"Negative samples ->\n{neg_dir}\n")
        _report(f"Positive samples ->\n{pos_dir}\n\n")

        # Plotting
        _report("Step 3/3: Making plots...\n")

        for ind, senu in enumerate(serial_numbers, start=0):
            if _cancelled():
                _report("Cancel requested. Stopping...")
                break

            errorlist, dclass = plot_anomaly(
                test_seq,
                test_pred,
                test_errors,
                ind,
                size_window,
                step_window,
                n_windows_per_ts,
                sec_params["threshold1"],
                sec_params["threshold2"],
                str(sec_dir),
                senu,
                config.test_name,
                section,
                nb_ts_origine,
                nb_feature,
                _cancelled,
                config.create_plot,
            )

            # Save section data for HTML report
            # Get anomaly scores for this time series
            start_win = ind * n_windows_per_ts
            end_win = (ind + 1) * n_windows_per_ts
            ts_scores = test_errors[start_win:end_win].tolist()

            # Build anomaly windows with positions
            anomaly_windows = []
            for (relative_start, relative_end), score in zip(window_bounds, ts_scores):
                win_start = sec_params["start"] + int(relative_start)
                win_end = sec_params["start"] + int(relative_end)
                anomaly_windows.append({
                    "start": win_start,
                    "end": win_end,
                    "score": score,
                    "threshold1": sec_params["threshold1"],
                    "threshold2": sec_params["threshold2"],
                })

            save_section_data(
                run_dir=run_dir,
                serial_number=str(senu),
                test_name=config.test_name,
                section_name=section,
                section_start=sec_params["start"],
                section_end=sec_params["end"],
                anomaly_windows=anomaly_windows,
                is_anomaly=dclass == 1,
            )

            if _cancelled():
                _report("Cancel requested. Stopping...")
                break

            if errorlist:
                errors.extend(errorlist)

        # cleanup per section
        del time, test, model_best, test_loader, test_seq, test_pred, test_errors
        gc.collect()

        _progress(base_prog + per_section * (si + 1))

    # -------------------------
    # Deduplicate + write file
    # -------------------------

    if _cancelled():
        _report("Run cancelled. Skipping final report generation.")
        return None

    errors = remove_duplicates_dict_list(errors)
    errors = sort_errors_by_section_order(errors, sections)

    _report("\n\nERRORS:\n\n")
    for i, error in enumerate(errors):
        _report(f"Error {i+1}:")
        _report(f"  Serial Number: {error['serial_number']}")
        _report(f"  Test Name: {error['test_name']}")
        _report(f"  Section: {error['section']}")
        _report("-" * 30)

    with open(f"{run_dir}/errors.txt", "w") as file:
        for i, error in enumerate(errors):
            file.write(f"Error {i+1}:\n")
            file.write(f"  Serial Number: {error['serial_number']}\n")
            file.write(f"  Test Name: {error['test_name']}\n")
            file.write(f"  Section: {error['section']}\n")
            file.write("-" * 30 + "\n")

    # Batch runs render combined HTML reports after every test has finished.
    dashboard_paths: Dict[str, str] = {}

    if not defer_html_outputs:
        _report("\nGenerating HTML reports...\n")
        html_files = generate_all_html_reports(
            run_dir=run_dir,
            test_name=config.test_name,
            input_folder=config.folder,
            device_series=config.device_series,
            signal_map=signal_map,
            report_callback=_report,
        )
        if html_files:
            _report(f"Generated {len(html_files)} HTML report(s) in {run_dir / 'reports' / 'html'}\n")
        else:
            _report("No HTML reports generated.\n")

    if config.create_pdf and not defer_pdf_outputs:
        _report("\nGenerating PDF reports...\n")
        pdf_files = generate_all_pdf_reports(
            run_dir=run_dir,
            test_name=config.test_name,
            device_series=config.device_series,
            run_mode=("Batch" if batch_timestamp else "Single"),
        )
        if pdf_files:
            _report(f"Generated {len(pdf_files)} PDF report(s) in {run_dir / 'reports' / 'pdf'}\n")
        else:
            _report("No PDF reports generated.\n")

    if not defer_html_outputs:
        dashboard_paths = generate_run_dashboard(
            run_dir=run_dir,
            device_series=config.device_series,
            test_name=config.test_name,
        )
        _report(f"Run dashboard: {dashboard_paths['index_path']}\n")
        _report(f"Run summary JSON: {dashboard_paths['summary_path']}\n")

    _progress(1.0)
    dashboard_index = dashboard_paths["index_path"] if dashboard_paths else ""
    return {
        "signal_map": signal_map,
        "serial_numbers": all_serial_numbers,
        "dashboard_index": dashboard_index,
        "run_dir": str(run_dir),
    }


def run_all_tests_for_device(
    device_series: str,
    input_folder: str,
    create_plot: bool = False,
    create_pdf: bool = False,
    report: Optional[Callable[[str], None]] = None,
    set_progress: Optional[Callable[[float], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Optional[Dict[str, str]]:
    """
    Execute all tests for a device and generate combined HTML reports.
    
    Output structure:
        outputs/batch/{device_series}/{timestamp}/
            {test_name_1}/
                {section_1}/
                    0/
                    1/
                {section_2}/
                    0/
                    1/
                errors.txt
            {test_name_2}/
                ...
    """
    
    def _report(msg: str) -> None:
        if report:
            report(msg)
    
    def _progress(x: float) -> None:
        if set_progress:
            set_progress(max(0.0, min(1.0, x)))
    
    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()
    
    tests = CFG.get_tests_for_device(device_series)
    
    if not tests:
        raise RuntimeError(f"No tests configured for device: {device_series}")
    
    _report(f"Starting batch run for {device_series}")
    _report(f"Tests to run: {', '.join(tests)}")
    _report(f"Total: {len(tests)} test(s)\n")
    
    base_dir = Path.cwd() / "outputs" / "batch" / device_series
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    
    _report(f"Output directory: {run_dir}\n")
    
    errors = []
    signal_maps_by_test: Dict[str, Dict[str, Any]] = {}
    per_test_progress = 1.0 / len(tests)
    report_executor = ThreadPoolExecutor(max_workers=min(4, max(1, len(tests))))
    
    try:
        for ti, test_name in enumerate(tests):
            if _cancelled():
                _report("Cancel requested. Stopping...")
                break
            
            _report("\n" + "=" * 50)
            _report(f"Running test {ti + 1}/{len(tests)}: {test_name}")
            _report("=" * 50 + "\n")
            
            config = UserConfig(
                folder=input_folder,
                device_series=device_series,
                test_name=test_name,
                create_plot=create_plot,
                create_pdf=create_pdf,
            )
            
            try:
                run_result = run_anomaly_detection(
                    config,
                    report=report,
                    set_progress=lambda x, t=ti: _progress(t * per_test_progress + x * per_test_progress),
                    cancel_event=cancel_event,
                    output_subdir=f"batch/{device_series}",
                    batch_timestamp=timestamp,
                    defer_html_outputs=True,
                    defer_pdf_outputs=create_pdf,
                )
                if run_result and run_result.get("signal_map") is not None:
                    signal_maps_by_test[test_name] = run_result["signal_map"]
                if _cancelled():
                    break
                    
            except InterruptedError:
                _report(f"Cancelled during test {test_name}.")
                break
            except Exception as e:
                _report(f"ERROR in test {test_name}: {e}")
                errors.append({
                    "test_name": test_name,
                    "error": str(e)
                })
            
            _progress((ti + 1) * per_test_progress)

    finally:
        report_executor.shutdown(wait=not _cancelled(), cancel_futures=_cancelled())
    
    if errors:
        _report("\n\nBATCH RUN ERRORS:\n")
        for error in errors:
            _report(f"  Test {error['test_name']}: {error['error']}")

    if not _cancelled():
        _report("\nGenerating batch HTML reports...\n")
        html_files = generate_batch_html_reports(
            batch_run_dir=run_dir,
            device_series=device_series,
            test_names=tests,
            input_folder=input_folder,
            signal_maps_by_test=signal_maps_by_test,
            report_callback=_report,
        )
        if html_files:
            _report(f"Generated {len(html_files)} batch HTML report(s) in {run_dir / 'reports' / 'html'}\n")
        else:
            _report("No batch HTML reports generated.\n")

    if create_pdf and not _cancelled():
        _report("\nGenerating batch PDF reports...\n")
        pdf_files = generate_batch_pdf_reports(
            batch_run_dir=run_dir,
            device_series=device_series,
            test_names=tests,
        )
        if pdf_files:
            _report(f"Generated {len(pdf_files)} batch PDF report(s) in {run_dir / 'reports' / 'pdf'}\n")
        else:
            _report("No batch PDF reports generated.\n")

    if not _cancelled():
        dashboard_paths = generate_batch_dashboard(
            batch_run_dir=run_dir,
            device_series=device_series,
            test_names=tests,
        )
        _report(f"Batch dashboard: {dashboard_paths['index_path']}\n")
        _report(f"Batch summary JSON: {dashboard_paths['summary_path']}\n")
    
    if _cancelled():
        _report("\nBatch run cancelled.")
        return None

    _report("\nBatch run completed.")
    _progress(1.0)
    dashboard_index = dashboard_paths["index_path"]
    return {"dashboard_index": dashboard_index}
