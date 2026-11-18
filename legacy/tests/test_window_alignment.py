"""Check original-sample positions through loading, inference, and Plotly."""

import json

import numpy as np
import pytest
import torch

from scripts.create_dat_file import create_dat_from_signal
from src.pipeline import runner
from src.visualization import html_report


class ZeroReconstructor(torch.nn.Module):
    """A deterministic reference model: only injected spikes have nonzero MSE."""

    def forward(self, data):
        return torch.zeros_like(data)


@pytest.mark.parametrize("resample_freq", ["1", "2", "2.5", "5"])
def test_fake_spikes_stay_inside_plotly_error_windows(tmp_path, monkeypatch, resample_freq):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    spikes = {"SYNTHETIC_A": 301, "SYNTHETIC_B": 501}
    signals = {}
    for serial, spike in spikes.items():
        signal = np.zeros(1000)
        signal[spike] = 10.0
        signals[serial] = signal.tolist()
        create_dat_from_signal(
            signals[serial], str(input_dir / f"{serial}.dat"),
            device_series="alignment_device", serial_number=serial, test_name="test1",
        )

    section = {
        "start": 101, "end": 704, "size_window": 10, "step_window": 5,
        "batch_size": 17, "transfo": ["mean"], "resample_freq": resample_freq,
        "hidden_size": 1, "num_layers": 1, "dropout": 0,
        "model_path": "unused_reference_model", "threshold1": 0.1, "threshold2": 0.2,
    }
    monkeypatch.setitem(runner.CFG.CONFIG, "alignment_device", {
        "test1": {"expected_len": 1000, "sections_order": ["section"], "sections": {"section": section}},
    })
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner, "device", torch.device("cpu"))
    monkeypatch.setattr(runner, "LSTMAutoEncoder", lambda **kwargs: ZeroReconstructor())
    monkeypatch.setattr(runner.torch, "load", lambda *args, **kwargs: {"model_state_dict": {}})
    # Keep actual preprocessing, MSE, JSON, Plotly and HTML generation; avoid PNG I/O
    # and process startup, which do not affect the coordinates being tested.
    monkeypatch.setattr("src.visualization.plots.plt.savefig", lambda *args, **kwargs: None)
    monkeypatch.setattr(html_report, "_run_parallel_tasks", lambda tasks, fn: [fn(task) for task in tasks])

    result = runner.run_anomaly_detection(runner.UserConfig(
        folder=str(input_dir), device_series="alignment_device", test_name="test1",
    ))
    run_dir = tmp_path / result["run_dir"]
    for serial, spike in spikes.items():
        data = json.loads((run_dir / "reports" / "section_data" / f"{serial}.json").read_text())
        windows = data["sections"][0]["anomaly_windows"]
        red_windows = [window for window in windows if window["score"] > section["threshold2"]]
        assert red_windows, "The reference model must detect the injected spike"
        assert all(window["start"] <= spike < window["end"] for window in red_windows)
        other_spike = next(value for key, value in spikes.items() if key != serial)
        assert all(not (window["start"] <= other_spike < window["end"]) for window in red_windows)
        assert all(section["start"] <= window["start"] < window["end"] <= section["end"] for window in windows)

        figure = html_report._build_signal_figure(serial, "test1", data, signals[serial])
        red_shapes = [shape for shape in figure.layout.shapes if shape.type == "rect"]
        assert len(red_shapes) == len(red_windows)
        assert all(shape.x0 <= spike < shape.x1 for shape in red_shapes)
        assert all(not (shape.x0 <= section["start"] + 1 < shape.x1) for shape in red_shapes)
        assert all(not (shape.x0 <= section["end"] - 2 < shape.x1) for shape in red_shapes)
        assert (run_dir / "reports" / "html" / f"{serial}.html").is_file()
