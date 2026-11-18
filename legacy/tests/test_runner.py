"""
Tests for batch runner orchestration.
"""

import sys
import types
from pathlib import Path
import json

import pytest
import torch


def _install_reportlab_stub() -> None:
    """Install a minimal reportlab stub so runner imports in test environments."""
    if "reportlab" in sys.modules:
        return

    reportlab = types.ModuleType("reportlab")
    lib = types.ModuleType("reportlab.lib")
    platypus = types.ModuleType("reportlab.platypus")
    enums = types.ModuleType("reportlab.lib.enums")
    styles = types.ModuleType("reportlab.lib.styles")
    units = types.ModuleType("reportlab.lib.units")
    pagesizes = types.ModuleType("reportlab.lib.pagesizes")
    colors = types.ModuleType("reportlab.lib.colors")

    class DummyColor:
        pass

    class DummyTableStyle:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class DummyParagraphStyle:
        def __init__(self, name, parent=None, **kwargs):
            self.name = name
            self.parent = parent
            self.kwargs = kwargs

    class DummyDoc:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def build(self, *args, **kwargs):
            return None

    def dummy_flowable(*args, **kwargs):
        return {"args": args, "kwargs": kwargs}

    colors.Color = DummyColor
    colors.HexColor = lambda value: value
    colors.white = "white"
    colors.black = "black"
    pagesizes.A4 = ("A4W", "A4H")
    pagesizes.landscape = lambda size: size
    units.inch = 1
    units.cm = 1
    enums.TA_CENTER = 1
    styles.getSampleStyleSheet = lambda: {"Heading1": object(), "Heading2": object(), "Heading3": object(), "BodyText": object()}
    styles.ParagraphStyle = DummyParagraphStyle
    platypus.SimpleDocTemplate = DummyDoc
    platypus.Table = dummy_flowable
    platypus.TableStyle = DummyTableStyle
    platypus.Paragraph = dummy_flowable
    platypus.Spacer = dummy_flowable
    platypus.Image = dummy_flowable
    platypus.PageBreak = dummy_flowable
    platypus.KeepTogether = dummy_flowable
    platypus.LongTable = dummy_flowable

    sys.modules["reportlab"] = reportlab
    sys.modules["reportlab.lib"] = lib
    sys.modules["reportlab.lib.colors"] = colors
    sys.modules["reportlab.lib.pagesizes"] = pagesizes
    sys.modules["reportlab.lib.styles"] = styles
    sys.modules["reportlab.lib.units"] = units
    sys.modules["reportlab.lib.enums"] = enums
    sys.modules["reportlab.platypus"] = platypus


_install_reportlab_stub()

from src.pipeline import runner
from tests.test_loader import create_test_dat_file


class TestEmptySignals:
    def test_empty_signal_never_loads_or_runs_a_model(self, tmp_path, monkeypatch):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        create_test_dat_file(str(input_dir / "empty.dat"), "device1", "EMPTY", "test1", 0)

        def forbidden(*args, **kwargs):
            pytest.fail("Empty measurements must not enter preprocessing or models")

        for name in ("preprocessing_with_bounds", "LSTMAutoEncoder", "get_avg_pred"):
            monkeypatch.setattr(runner, name, forbidden)
        monkeypatch.setattr(runner.torch, "load", forbidden)
        monkeypatch.chdir(tmp_path)
        progress = []
        result = runner.run_anomaly_detection(
            runner.UserConfig(str(input_dir), "device1", "test1"),
            set_progress=progress.append,
        )

        assert result["serial_numbers"] == ["EMPTY"]
        assert progress[-1] == 1.0
        run_dir = Path(result["run_dir"])
        assert not list(run_dir.glob("*/0"))
        assert not (run_dir / "reports" / "section_data").exists()
        summary = json.loads(Path(result["dashboard_index"]).with_name("summary.json").read_text(encoding="utf-8"))
        assert summary["serials"][0]["status"] == "no_data"
        assert summary["totals"]["normal_serials"] == 0
        assert summary["totals"]["anomalous_serials"] == 0
        report = run_dir / "reports" / "html" / "EMPTY.html"
        assert "No data is available for this test." in report.read_text(encoding="utf-8")

    def test_mixed_signals_score_only_nonempty_samples_in_order(self, tmp_path, monkeypatch):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        create_test_dat_file(str(input_dir / "a.dat"), "device1", "EMPTY", "test1", 0)
        create_test_dat_file(str(input_dir / "b.dat"), "device1", "ZERO", "test1", 22528)
        create_test_dat_file(str(input_dir / "c.dat"), "device1", "ONES", "test1", 22528)
        # A measured all-zero signal remains eligible for inference.
        import gzip
        from proto.generated.schema_pb2 import Array_ProtoDevice
        root = Array_ProtoDevice()
        root.ParseFromString(gzip.decompress((input_dir / "b.dat").read_bytes()))
        root.items[0].testResult[0].signals[0].data[:] = [0.0] * 22528
        (input_dir / "b.dat").write_bytes(gzip.compress(root.SerializeToString()))

        params = {"start": 0, "end": 8, "batch_size": 10, "step_window": 4,
                  "size_window": 4, "resample_freq": "1", "transfo": ["mean"],
                  "num_layers": 1, "hidden_size": 2, "model_path": "unused",
                  "threshold1": 0.35, "threshold2": 0.36}
        monkeypatch.setattr(runner.CFG, "get_sections_order", lambda *args: ["section"])
        monkeypatch.setattr(runner.CFG, "get_section_params", lambda *args: params)

        class FakeModel:
            def __init__(self, **kwargs):
                pass

            def to(self, device):
                return self

            def load_state_dict(self, state):
                pass

        scored = []
        def score(loader, data, *args, **kwargs):
            scored.append(data.clone())
            return data.clone(), torch.zeros(len(data))

        plotted = []
        def plot(*args):
            plotted.append(args[10])
            return [], 0

        monkeypatch.setattr(runner, "LSTMAutoEncoder", FakeModel)
        monkeypatch.setattr(runner.torch, "load", lambda *args, **kwargs: {"model_state_dict": {}})
        monkeypatch.setattr(runner, "get_avg_pred", score)
        monkeypatch.setattr(runner, "plot_anomaly", plot)
        monkeypatch.chdir(tmp_path)

        result = runner.run_anomaly_detection(
            runner.UserConfig(str(input_dir), "device1", "test1"),
            defer_html_outputs=True,
        )

        assert plotted == ["ZERO", "ONES"]
        assert len(scored) == 1
        assert scored[0].shape == (4, 4, 1)
        assert torch.all(scored[0][:2] == 0)
        assert torch.all(scored[0][2:] == 1)
        assert result["signal_map"]["EMPTY"] == []
        assert not (Path(result["run_dir"]) / "reports" / "section_data" / "EMPTY.json").exists()


class TestRunAllTestsForDevice:
    """Tests for batch-mode report generation behavior."""

    def test_missing_tests_are_incomplete_after_loading_and_inference(self, tmp_path, monkeypatch):
        import gzip
        from proto.generated.schema_pb2 import Array_ProtoDevice
        from src.visualization import html_report

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        device = "missing_test_device"
        serials = {"SC_37_missing_test1": "test2", "SC_38_missing_test2": "test1"}
        for serial, present_test in serials.items():
            create_test_dat_file(str(input_dir / f"{serial}.dat"), device, serial, present_test, 8)
        complete = Array_ProtoDevice()
        complete.ParseFromString(gzip.decompress((input_dir / "SC_38_missing_test2.dat").read_bytes()))
        complete.items[0].serialNumber = "COMPLETE"
        extra = complete.items[0].testResult.add()
        extra.testName = "test2"
        extra.signals.add(name="signal1").data.extend([1.0] * 8)
        (input_dir / "COMPLETE.dat").write_bytes(gzip.compress(complete.SerializeToString()))

        params = {"start": 0, "end": 8, "batch_size": 10, "step_window": 4,
                  "size_window": 4, "resample_freq": "1", "transfo": ["mean"],
                  "num_layers": 1, "hidden_size": 2, "model_path": "unused",
                  "threshold1": 0.35, "threshold2": 0.36}
        monkeypatch.setitem(runner.CFG.CONFIG, device, {
            test: {"expected_len": 8, "sections_order": ["section"], "sections": {"section": params}}
            for test in ("test1", "test2")})

        class IdentityModel(torch.nn.Module):
            def forward(self, data):
                return data

        monkeypatch.setattr(runner, "LSTMAutoEncoder", lambda **kwargs: IdentityModel())
        monkeypatch.setattr(runner.torch, "load", lambda *args, **kwargs: {"model_state_dict": {}})
        monkeypatch.setattr(runner, "plot_anomaly", lambda *args: ([], 0))
        monkeypatch.setattr(html_report, "_run_parallel_tasks", lambda tasks, fn: [fn(task) for task in tasks])
        monkeypatch.chdir(tmp_path)

        result = runner.run_all_tests_for_device(device, str(input_dir))

        dashboard = Path(result["dashboard_index"])
        summary = json.loads(dashboard.with_name("summary.json").read_text(encoding="utf-8"))
        rows = {row["serial_number"]: row for row in summary["serials"]}
        assert rows["COMPLETE"]["status"] == "normal"
        assert summary["totals"]["normal_serials"] == 1
        assert summary["totals"]["incomplete_serials"] == 2
        for serial, present_test in serials.items():
            missing_test = "test1" if present_test == "test2" else "test2"
            assert rows[serial]["status"] == "incomplete"
            assert rows[serial]["missing_tests"] == [missing_test]
            assert rows[serial]["test_count"] == 2
            assert rows[serial]["evaluated_tests"] == 1
            content = (dashboard.parent / "html" / f"{serial}.html").read_text(encoding="utf-8")
            assert f"{missing_test} — Missing Test" in content

    def test_batch_generates_only_combined_reports(self, tmp_path, monkeypatch):
        batch_root = tmp_path / "outputs"
        batch_timestamp = "20260720_183348"
        batch_dir = batch_root / "batch" / "device1" / batch_timestamp

        combined_pdf_calls = []
        per_test_pdf_calls = []
        per_test_html_calls = []
        combined_html_calls = []

        class FixedDatetime:
            @staticmethod
            def now():
                class _Value:
                    @staticmethod
                    def strftime(_fmt: str) -> str:
                        return batch_timestamp

                return _Value()

        def fake_run_anomaly_detection(
            config,
            report=None,
            set_progress=None,
            cancel_event=None,
            output_subdir="single",
            batch_timestamp=None,
            defer_html_outputs=False,
            defer_pdf_outputs=False,
        ):
            run_dir = batch_dir / config.test_name
            (run_dir / "reports" / "section_data").mkdir(parents=True, exist_ok=True)
            return {
                "signal_map": {"SN001": [0.0, 1.0]},
                "serial_numbers": ["SN001"],
                "dashboard_index": "",
                "run_dir": str(run_dir),
            }

        def fake_generate_all_pdf_reports(*args, **kwargs):
            per_test_pdf_calls.append((args, kwargs))
            return ["unexpected"]

        def fake_generate_all_html_reports(*args, **kwargs):
            per_test_html_calls.append((args, kwargs))
            return []

        def fake_generate_batch_html_reports(batch_run_dir, device_series, test_names, input_folder, signal_maps_by_test=None, report_callback=None):
            combined_html_calls.append(
                {
                    "batch_run_dir": batch_run_dir,
                    "device_series": device_series,
                    "test_names": list(test_names),
                    "signal_maps_by_test": signal_maps_by_test or {},
                }
            )
            reports_dir = Path(batch_run_dir) / "reports" / "html"
            reports_dir.mkdir(parents=True, exist_ok=True)
            html_path = reports_dir / "SN001.html"
            html_path.write_text("<html></html>", encoding="utf-8")
            return [str(html_path)]

        def fake_generate_batch_pdf_reports(batch_run_dir, device_series, test_names, threshold1=0.35, threshold2=0.36):
            combined_pdf_calls.append(
                {
                    "batch_run_dir": batch_run_dir,
                    "device_series": device_series,
                    "test_names": list(test_names),
                }
            )
            reports_dir = Path(batch_run_dir) / "reports" / "pdf"
            reports_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = reports_dir / "SN001_report.pdf"
            pdf_path.write_text("pdf", encoding="utf-8")
            return [str(pdf_path)]

        def fake_generate_batch_dashboard(batch_run_dir, device_series, test_names):
            reports_dir = Path(batch_run_dir) / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            index_path = reports_dir / "index.html"
            summary_path = reports_dir / "summary.json"
            index_path.write_text("<html></html>", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            return {"index_path": str(index_path), "summary_path": str(summary_path)}

        monkeypatch.setattr(runner.CFG, "get_tests_for_device", lambda device: ["test1", "test2"])
        monkeypatch.setattr(runner, "datetime", FixedDatetime)
        monkeypatch.setattr(runner, "run_anomaly_detection", fake_run_anomaly_detection)
        monkeypatch.setattr(runner, "generate_all_pdf_reports", fake_generate_all_pdf_reports)
        monkeypatch.setattr(runner, "generate_all_html_reports", fake_generate_all_html_reports)
        monkeypatch.setattr(runner, "generate_batch_html_reports", fake_generate_batch_html_reports)
        monkeypatch.setattr(runner, "generate_batch_pdf_reports", fake_generate_batch_pdf_reports)
        monkeypatch.setattr(runner, "generate_batch_dashboard", fake_generate_batch_dashboard)
        monkeypatch.chdir(tmp_path)

        result = runner.run_all_tests_for_device(
            device_series="device1",
            input_folder=str(tmp_path / "input"),
            create_pdf=True,
        )

        assert result is not None
        assert result["dashboard_index"].endswith("index.html")
        assert per_test_pdf_calls == []
        assert per_test_html_calls == []
        assert len(combined_html_calls) == 1
        assert len(combined_pdf_calls) == 1
        assert combined_html_calls[0]["batch_run_dir"] == batch_dir
        assert combined_html_calls[0]["device_series"] == "device1"
        assert combined_html_calls[0]["test_names"] == ["test1", "test2"]
        assert set(combined_html_calls[0]["signal_maps_by_test"].keys()) == {"test1", "test2"}
        assert combined_pdf_calls[0]["batch_run_dir"] == batch_dir
        assert combined_pdf_calls[0]["device_series"] == "device1"
        assert combined_pdf_calls[0]["test_names"] == ["test1", "test2"]
        assert (batch_dir / "reports" / "index.html").exists()
        assert (batch_dir / "reports" / "html" / "SN001.html").exists()
        assert (batch_dir / "reports" / "pdf" / "SN001_report.pdf").exists()
        assert not (batch_dir / "test1" / "reports" / "html").exists()
        assert not (batch_dir / "test2" / "reports" / "html").exists()
        assert not (batch_dir / "test1" / "reports" / "pdf").exists()
        assert not (batch_dir / "test2" / "reports" / "pdf").exists()


class TestRunnerHelpers:
    def test_remove_duplicates_preserves_first_seen_order(self):
        entries = [
            {"serial_number": "SN001", "test_name": "test2", "section": "09_section_09"},
            {"serial_number": "SN002", "test_name": "test2", "section": "03_section_03"},
            {"serial_number": "SN001", "test_name": "test2", "section": "09_section_09"},
            {"serial_number": "SN003", "test_name": "test2", "section": "13_section_13"},
        ]

        result = runner.remove_duplicates_dict_list(entries)

        assert result == [
            {"serial_number": "SN001", "test_name": "test2", "section": "09_section_09"},
            {"serial_number": "SN002", "test_name": "test2", "section": "03_section_03"},
            {"serial_number": "SN003", "test_name": "test2", "section": "13_section_13"},
        ]

    def test_sort_errors_by_section_order_preserves_within_section_order(self):
        entries = [
            {"serial_number": "SN001", "test_name": "test2", "section": "09_section_09"},
            {"serial_number": "SN002", "test_name": "test2", "section": "03_section_03"},
            {"serial_number": "SN003", "test_name": "test2", "section": "09_section_09"},
            {"serial_number": "SN004", "test_name": "test2", "section": "05_section_05"},
        ]

        result = runner.sort_errors_by_section_order(
            entries,
            ["03_section_03", "05_section_05", "09_section_09"],
        )

        assert result == [
            {"serial_number": "SN002", "test_name": "test2", "section": "03_section_03"},
            {"serial_number": "SN004", "test_name": "test2", "section": "05_section_05"},
            {"serial_number": "SN001", "test_name": "test2", "section": "09_section_09"},
            {"serial_number": "SN003", "test_name": "test2", "section": "09_section_09"},
        ]
