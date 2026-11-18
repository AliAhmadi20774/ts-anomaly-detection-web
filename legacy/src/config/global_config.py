"""
Global configuration module for time series anomaly detection system.

This module contains:
- Device to test mapping
- Specific settings for each device/test/section combination
- Helper functions for accessing configurations

Configuration structure:
    CONFIG[device][test]["sections"][section_name] = {...params...}

Main variables:
    CONFIG: Complete configuration dictionary with all required fields
"""

from __future__ import annotations
import copy
from pathlib import Path
import sys
from typing import Any


def resource_path(relative: str) -> Path:
    """
    Resolve a resource path for both:
      - normal python run (uses the project root)
      - PyInstaller bundle (uses sys._MEIPASS)
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]
    return base / relative


# ---------- Legacy duplicated UI mapping ----------
# The UI device/test lists should now be derived directly from CONFIG.
# Keep the old mapping here only as commented reference during migration.
#
# DEVICE_TEST_MAPPING: dict[str, list[str]] = {
#     "device1": ["test1", "test2"],
#     "device2": ["test5", "test6"],
#     "device3": ["test7", "test8", "test9"],
#     "device4": ["test10"],
# }


# ---------- 3) per device/test/section params ----------
# Suggested structure:
# CONFIG[device][test]["sections"][section_name] = {...params...}
#
# All parameters must be explicitly configured. No defaults are applied.

CONFIG: dict[str, dict[str, dict]] = {
    "device1": {
        "test1": {
            "sections_order": [
                "01_section_01", "02_section_02", "03_section_03", "04_section_04",
                "05_section_05", "06_section_06", "07_section_07", "08_section_08",
                "09_section_09", "10_section_10", "11_section_11", "12_section_12",
                "13_section_13", "14_section_14"
            ],
            "expected_len": 22528,
            "sections": {
                "01_section_01": {
                    "start":0,
                    "end":1000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "02_section_02": {
                    "start":1000,
                    "end":2000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "03_section_03": {
                    "start":2000,
                    "end":3000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "04_section_04": {
                    "start":3000,
                    "end":4000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "05_section_05": {
                    "start":4000,
                    "end":5000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "06_section_06": {
                    "start":5000,
                    "end":6000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "07_section_07": {
                    "start":6000,
                    "end":7000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "08_section_08": {
                    "start":7000,
                    "end":8000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "09_section_09": {
                    "start":8000,
                    "end":9000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "10_section_10": {
                    "start":9000,
                    "end":10000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "11_section_11": {
                    "start":10000,
                    "end":11000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "12_section_12": {
                    "start":11000,
                    "end":12000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "13_section_13": {
                    "start":12000,
                    "end":13000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "14_section_14": {
                    "start":13000,
                    "end":14000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },
            }
        },
        "test2": {
            "sections_order": [
                "01_section_01", "02_section_02", "03_section_03", "04_section_04",
                "05_section_05", "06_section_06", "07_section_07", "08_section_08",
                "09_section_09", "10_section_10", "11_section_11", "12_section_12",
                "13_section_13", "14_section_14"
            ],
            "expected_len": 22528,
            "sections": {
                "01_section_01": {
                    "start":0,
                    "end":1000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "02_section_02": {
                    "start":1000,
                    "end":2000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "03_section_03": {
                    "start":2000,
                    "end":3000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "04_section_04": {
                    "start":3000,
                    "end":4000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "05_section_05": {
                    "start":4000,
                    "end":5000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "06_section_06": {
                    "start":5000,
                    "end":6000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "07_section_07": {
                    "start":6000,
                    "end":7000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "08_section_08": {
                    "start":7000,
                    "end":8000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "09_section_09": {
                    "start":8000,
                    "end":9000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "10_section_10": {
                    "start":9000,
                    "end":10000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "11_section_11": {
                    "start":10000,
                    "end":11000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "12_section_12": {
                    "start":11000,
                    "end":12000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "13_section_13": {
                    "start":12000,
                    "end":13000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

                "14_section_14": {
                    "start":13000,
                    "end":14000,
                    "batch_size": 100,
                    "step_window": 25,
                    "size_window": 50,
                    "resample_freq": "1",
                    "hidden_size": 300,
                    "num_layers": 1,
                    "dropout": 0.2,
                    "model_path": "checkpoints/device1/lstm_ae_epoch_1",
                    "threshold1": 0.35,
                    "threshold2": 0.36,
                    "transfo":["mean"],
                },

            }
        }
    }
}


DEFAULT_DEVICE = next(iter(CONFIG.keys()), "")
THRESHOLD_OVERRIDES: dict[tuple[str, str, str], dict[str, float]] = {}


def get_tests_for_device(device: str) -> list[str]:
    """Return configured tests directly from CONFIG."""
    return list(CONFIG.get(device, {}).keys())


def get_all_devices() -> list[str]:
    """Return configured devices directly from CONFIG."""
    return list(CONFIG.keys())





def _get_test_cfg(device_series: str, test_name: str) -> dict:
    if device_series not in CONFIG:
        raise KeyError(f"Device not found in CONFIG: {device_series}")
    if test_name not in CONFIG[device_series]:
        raise KeyError(f"Test not found in CONFIG for {device_series}: {test_name}")
    return CONFIG[device_series][test_name]


def get_sections_order(device_series: str, test_name: str) -> list[str]:
    """
    Returns ordered list of sections to run for this device/test.
    """
    test_cfg = _get_test_cfg(device_series, test_name)

    order = test_cfg.get("sections_order")
    sections: dict = test_cfg.get("sections", {})

    if order:
        # Execute only those that are actually defined in sections
        return [s for s in order if s in sections]

    # fallback: if order is not present, use section keys (sorted)
    return sorted(sections.keys())


def get_config_snapshot(apply_threshold_overrides: bool = True) -> dict[str, dict[str, dict]]:
    """Return a deep copy of CONFIG, optionally merged with runtime threshold overrides."""
    snapshot = copy.deepcopy(CONFIG)
    if not apply_threshold_overrides:
        return snapshot

    for (device_series, test_name, section_name), override_values in THRESHOLD_OVERRIDES.items():
        section_cfg = (
            snapshot
            .get(device_series, {})
            .get(test_name, {})
            .get("sections", {})
            .get(section_name)
        )
        if not section_cfg:
            continue
        section_cfg.update(override_values)
    return snapshot


def set_threshold_override(
    device_series: str,
    test_name: str,
    section_name: str,
    threshold1: float,
    threshold2: float,
) -> None:
    """Store runtime-only threshold overrides for one section."""
    _get_test_cfg(device_series, test_name)
    sections = CONFIG[device_series][test_name].get("sections", {})
    if section_name not in sections:
        raise KeyError(f"Section not found: {device_series}/{test_name}/{section_name}")

    THRESHOLD_OVERRIDES[(device_series, test_name, section_name)] = {
        "threshold1": float(threshold1),
        "threshold2": float(threshold2),
    }


def clear_threshold_override(device_series: str, test_name: str, section_name: str) -> None:
    """Remove the runtime-only threshold override for one section."""
    THRESHOLD_OVERRIDES.pop((device_series, test_name, section_name), None)


def has_threshold_override(device_series: str, test_name: str, section_name: str) -> bool:
    """Return whether a section has runtime threshold overrides."""
    return (device_series, test_name, section_name) in THRESHOLD_OVERRIDES


def get_section_params(device_series: str, test_name: str, section_name: str) -> dict[str, Any]:
    """
    Returns section params. All required fields must be explicitly configured.
    Raises KeyError for missing required fields.
    """
    test_cfg = _get_test_cfg(device_series, test_name)
    sections: dict = test_cfg.get("sections", {})

    if section_name not in sections:
        raise KeyError(f"Section not found: {device_series}/{test_name}/{section_name}")

    raw = dict(sections[section_name])  # copy
    raw.update(THRESHOLD_OVERRIDES.get((device_series, test_name, section_name), {}))

    # normalize transfo to list[str]
    if "transfo" not in raw:
        raise KeyError(f"transfo not configured for {device_series}/{test_name}/{section_name}")
    t = raw["transfo"]
    if isinstance(t, str):
        raw["transfo"] = [t]
    elif isinstance(t, list):
        raw["transfo"] = t
    else:
        raw["transfo"] = ["mean"]

    # make sure ints where needed
    for field in ["start", "end", "batch_size", "step_window", "size_window", "hidden_size", "num_layers"]:
        if field not in raw:
            raise KeyError(f"{field} not configured for {device_series}/{test_name}/{section_name}")
        raw[field] = int(raw[field])

    # dropout float with default 0
    raw["dropout"] = float(raw.get("dropout", 0))

    # thresholds float
    for field in ["threshold1", "threshold2"]:
        if field not in raw:
            raise KeyError(f"{field} not configured for {device_series}/{test_name}/{section_name}")
        raw[field] = float(raw[field])

    # resample_freq string
    if "resample_freq" not in raw:
        raise KeyError(f"resample_freq not configured for {device_series}/{test_name}/{section_name}")
    raw["resample_freq"] = str(raw["resample_freq"])

    # model_path string
    if "model_path" not in raw:
        raise KeyError(f"model_path not configured for {device_series}/{test_name}/{section_name}")
    raw["model_path"] = str(raw["model_path"])

    return raw



def get_expected_signal_len(device_series: str, test_name: str) -> int:
    """
    Gets expected_len from the test configuration.
    Raises KeyError if device, test, or expected_len is not configured.
    """
    test_cfg = _get_test_cfg(device_series, test_name)
    
    if "expected_len" not in test_cfg:
        raise KeyError(f"expected_len not configured for {device_series}/{test_name}")
    
    return int(test_cfg["expected_len"])
