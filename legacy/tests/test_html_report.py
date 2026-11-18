"""
Tests for HTML summary dashboard generation.
"""

import json
import pytest

from src.visualization.html_report import (
    MAX_PLOT_POINTS,
    PLOTLY_ASSET_NAME,
    _downsample_signal,
    _build_signal_figure,
    generate_batch_dashboard,
    generate_html_report,
    generate_all_html_reports,
    generate_batch_html_reports,
    generate_run_dashboard,
    write_signal_inventory,
)
import src.visualization.html_report as html_report


def _write_section_data(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _empty_inventory(reports_dir, serial="EMPTY"):
    write_signal_inventory(reports_dir, [{"serial_number": serial, "signal_length": 0,
        "expected_length": 22528, "length_matches_expected": False}])


class TestNoDataHtmlReports:
    @pytest.mark.parametrize("present_test", ["test1", "test2"])
    @pytest.mark.parametrize("has_anomaly", [False, True])
    def test_absent_expected_test_is_reported_and_never_classified_normal(self, tmp_path, present_test, has_anomaly):
        missing_test = "test2" if present_test == "test1" else "test1"
        serial = "ONE_TEST_ONLY"
        _write_section_data(tmp_path / present_test / "reports" / "section_data" / f"{serial}.json", {
            "serial_number": serial, "test_name": present_test, "sections": [{
                "section_name": "section", "section_start": 0, "section_end": 2,
                "is_anomaly": has_anomaly, "anomaly_windows": []}]})

        generate_batch_html_reports(tmp_path, "device1", ["test1", "test2"], "unused",
            signal_maps_by_test={present_test: {serial: [1, 2]}, missing_test: {}})
        generate_batch_dashboard(tmp_path, "device1", ["test1", "test2"])

        summary = json.loads((tmp_path / "reports" / "summary.json").read_text(encoding="utf-8"))
        row = summary["serials"][0]
        assert row["status"] == ("anomaly" if has_anomaly else "incomplete")
        assert row["has_anomaly"] is has_anomaly
        assert row["missing_tests"] == [missing_test]
        assert row["test_count"] == 2
        assert row["evaluated_tests"] == 1
        missing = next(test for test in row["tests"] if test["test_name"] == missing_test)
        assert missing["status"] == "missing_test"
        assert missing["total_sections"] == 0
        assert missing["has_anomaly"] is False
        assert missing["signal_length"] is None
        assert summary["totals"]["normal_serials"] == 0
        content = (tmp_path / "reports" / "html" / f"{serial}.html").read_text(encoding="utf-8")
        assert f"{missing_test} — Missing Test" in content
        assert "This test is missing. Model evaluation was not performed." in content
        assert f'data-tab="tab-{present_test}-{serial}"' in content

    def test_single_no_data_has_report_and_is_not_normal(self, tmp_path):
        _empty_inventory(tmp_path / "reports")
        files = generate_all_html_reports(tmp_path, "test1", "unused", "device1", signal_map={"EMPTY": []})
        assert len(files) == 1
        content = (tmp_path / "reports" / "html" / "EMPTY.html").read_text(encoding="utf-8")
        assert "No data is available for this test." in content
        assert "Not evaluated" in content
        assert "Original Signal" not in content
        assert "plotly-graph-div" not in content
        assert generate_html_report(tmp_path, "EMPTY", "test1") == files[0]

        generate_run_dashboard(tmp_path, "device1", "test1")
        summary = json.loads((tmp_path / "reports" / "summary.json").read_text(encoding="utf-8"))
        row = summary["serials"][0]
        assert row["status"] == "no_data"
        assert row["has_anomaly"] is False
        assert row["has_length_warning"] is False
        assert row["html_report_path"] == "html/EMPTY.html"
        assert summary["totals"]["normal_serials"] == 0
        assert summary["totals"]["anomalous_serials"] == 0
        assert summary["totals"]["no_data_serials"] == 1
        dashboard = (tmp_path / "reports" / "index.html").read_text(encoding="utf-8")
        assert 'id="missing-data-serials"' not in dashboard
        assert 'id="extra-total"' not in dashboard

    def test_batch_keeps_empty_test_tab_alongside_evaluated_test(self, tmp_path, monkeypatch):
        # Include another serial whose tests are all empty.
        write_signal_inventory(tmp_path / "test1" / "reports", [
            {"serial_number": serial, "signal_length": 0, "expected_length": 22528,
             "length_matches_expected": False} for serial in ("MIXED", "EMPTY")])
        _empty_inventory(tmp_path / "test2" / "reports", "EMPTY")
        _write_section_data(tmp_path / "test2" / "reports" / "section_data" / "MIXED.json", {
            "serial_number": "MIXED", "test_name": "test2", "sections": [{
                "section_name": "normal", "section_start": 0, "section_end": 2,
                "is_anomaly": False, "anomaly_windows": []}]})
        monkeypatch.setattr(html_report, "_run_parallel_tasks", lambda tasks, fn: [fn(task) for task in tasks])
        files = generate_batch_html_reports(tmp_path, "device1", ["test1", "test2"], "unused",
            signal_maps_by_test={"test1": {"MIXED": [], "EMPTY": []}, "test2": {"MIXED": [1, 2], "EMPTY": []}})
        assert len(files) == 2
        content = (tmp_path / "reports" / "html" / "MIXED.html").read_text(encoding="utf-8")
        assert "test1 — No Data" in content
        assert "No data is available for this test." in content
        assert 'data-tab="tab-test2-MIXED"' in content
        assert "Original Signal" in content

        generate_batch_dashboard(tmp_path, "device1", ["test1", "test2"])
        summary = json.loads((tmp_path / "reports" / "summary.json").read_text(encoding="utf-8"))
        rows = {row["serial_number"]: row for row in summary["serials"]}
        assert rows["EMPTY"]["status"] == "no_data"
        assert rows["MIXED"]["status"] == "incomplete"
        assert rows["MIXED"]["tests"][0]["status"] == "no_data"
        assert rows["MIXED"]["tests"][1]["status"] == "normal"
        assert summary["totals"]["normal_serials"] == 0
        assert summary["totals"]["anomalous_serials"] == 0
        assert summary["totals"]["no_data_serials"] == 1
        assert summary["totals"]["incomplete_serials"] == 1
        assert summary["totals"]["tests_without_data"] == 3


class TestGenerateRunDashboard:
    """Tests for single-run dashboard generation."""

    def test_writes_summary_and_index(self, tmp_path):
        run_dir = tmp_path / "single_run"
        reports_dir = run_dir / "reports"
        (reports_dir / "html").mkdir(parents=True)
        (reports_dir / "pdf").mkdir(parents=True)
        write_signal_inventory(
            reports_dir,
            [
                {
                    "serial_number": "SN001",
                    "signal_length": 22528,
                    "expected_length": 22528,
                    "length_matches_expected": True,
                }
            ],
        )

        _write_section_data(
            reports_dir / "section_data" / "SN001.json",
            {
                "serial_number": "SN001",
                "test_name": "test1",
                "sections": [
                    {
                        "section_name": "01_section",
                        "section_start": 0,
                        "section_end": 10,
                        "is_anomaly": True,
                        "anomaly_windows": [{"score": 0.48}],
                    },
                    {
                        "section_name": "02_section",
                        "section_start": 10,
                        "section_end": 20,
                        "is_anomaly": False,
                        "anomaly_windows": [{"score": 0.12}],
                    },
                ],
            },
        )
        (run_dir / "01_section" / "1").mkdir(parents=True)
        (run_dir / "01_section" / "1" / "SN001.png").write_text("png", encoding="utf-8")
        (reports_dir / "html" / "SN001.html").write_text("<html></html>", encoding="utf-8")
        (reports_dir / "pdf" / "SN001_report.pdf").write_text("pdf", encoding="utf-8")

        result = generate_run_dashboard(run_dir, "device1", "test1")

        summary_path = reports_dir / "summary.json"
        index_path = reports_dir / "index.html"
        assert result["summary_path"] == str(summary_path)
        assert result["index_path"] == str(index_path)
        assert summary_path.exists()
        assert index_path.exists()

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["totals"]["total_serials"] == 1
        assert summary["totals"]["anomalous_serials"] == 1
        assert summary["serials"][0]["serial_number"] == "SN001"
        assert summary["serials"][0]["has_anomaly"] is True
        assert summary["serials"][0]["html_report_path"] == "html/SN001.html"
        assert summary["serials"][0]["pdf_report_path"] == "pdf/SN001_report.pdf"
        assert summary["serials"][0]["anomaly_images"] == [
            {"label": "01_section", "path": "../01_section/1/SN001.png"}
        ]

        index_html = index_path.read_text(encoding="utf-8")
        assert "Anomaly Dashboard" in index_html
        assert "SN001" in index_html
        assert "../01_section/1/SN001.png" in index_html

    def test_shows_length_warning_without_section_data(self, tmp_path):
        run_dir = tmp_path / "single_run_warning"
        reports_dir = run_dir / "reports"
        write_signal_inventory(
            reports_dir,
            [
                {
                    "serial_number": "SNWARN",
                    "signal_length": 22000,
                    "expected_length": 22528,
                    "length_matches_expected": False,
                }
            ],
        )

        generate_run_dashboard(run_dir, "device1", "test1")

        summary = json.loads((reports_dir / "summary.json").read_text(encoding="utf-8"))
        assert summary["serials"][0]["serial_number"] == "SNWARN"
        assert summary["serials"][0]["has_length_warning"] is True
        assert summary["serials"][0]["signal_length"] == 22000
        assert summary["serials"][0]["expected_length"] == 22528

        index_html = (reports_dir / "index.html").read_text(encoding="utf-8")
        assert '"has_length_warning": true' in index_html.lower()
        assert '"signal_length": 22000' in index_html
        assert '"expected_length": 22528' in index_html


class TestGenerateBatchDashboard:
    """Tests for batch-run dashboard generation."""

    def test_writes_batch_summary_and_index(self, tmp_path):
        batch_dir = tmp_path / "batch_run"
        reports_dir = batch_dir / "reports"
        (reports_dir / "html").mkdir(parents=True)
        (reports_dir / "pdf").mkdir(parents=True)
        write_signal_inventory(
            batch_dir / "test1" / "reports",
            [
                {
                    "serial_number": "SN002",
                    "signal_length": 22528,
                    "expected_length": 22528,
                    "length_matches_expected": True,
                }
            ],
        )
        write_signal_inventory(
            batch_dir / "test2" / "reports",
            [
                {
                    "serial_number": "SN002",
                    "signal_length": 22528,
                    "expected_length": 22528,
                    "length_matches_expected": True,
                }
            ],
        )

        _write_section_data(
            batch_dir / "test1" / "reports" / "section_data" / "SN002.json",
            {
                "serial_number": "SN002",
                "test_name": "test1",
                "sections": [
                    {
                        "section_name": "01_section",
                        "section_start": 0,
                        "section_end": 10,
                        "is_anomaly": True,
                        "anomaly_windows": [{"score": 0.61}],
                    }
                ],
            },
        )
        _write_section_data(
            batch_dir / "test2" / "reports" / "section_data" / "SN002.json",
            {
                "serial_number": "SN002",
                "test_name": "test2",
                "sections": [
                    {
                        "section_name": "01_section",
                        "section_start": 0,
                        "section_end": 10,
                        "is_anomaly": False,
                        "anomaly_windows": [{"score": 0.18}],
                    }
                ],
            },
        )
        (batch_dir / "test1" / "reports" / "html").mkdir(parents=True, exist_ok=True)
        (batch_dir / "test2" / "reports" / "html").mkdir(parents=True, exist_ok=True)
        (batch_dir / "test1" / "01_section" / "1").mkdir(parents=True, exist_ok=True)
        (batch_dir / "test1" / "01_section" / "1" / "SN002.png").write_text("png", encoding="utf-8")
        (batch_dir / "test1" / "reports" / "html" / "SN002.html").write_text("<html></html>", encoding="utf-8")
        (batch_dir / "test2" / "reports" / "html" / "SN002.html").write_text("<html></html>", encoding="utf-8")
        (reports_dir / "html" / "SN002.html").write_text("<html></html>", encoding="utf-8")
        (reports_dir / "pdf" / "SN002_report.pdf").write_text("pdf", encoding="utf-8")

        result = generate_batch_dashboard(batch_dir, "device1", ["test1", "test2"])

        summary_path = reports_dir / "summary.json"
        index_path = reports_dir / "index.html"
        assert result["summary_path"] == str(summary_path)
        assert result["index_path"] == str(index_path)
        assert summary_path.exists()
        assert index_path.exists()

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["totals"]["total_serials"] == 1
        assert summary["totals"]["anomalous_serials"] == 1
        assert summary["totals"]["total_tests"] == 2
        assert summary["serials"][0]["serial_number"] == "SN002"
        assert summary["serials"][0]["anomalous_tests"] == 1
        assert summary["serials"][0]["html_report_path"] == "html/SN002.html"
        assert summary["serials"][0]["pdf_report_path"] == "pdf/SN002_report.pdf"
        assert len(summary["serials"][0]["tests"]) == 2
        assert summary["serials"][0]["tests"][0]["anomaly_images"] == [
            {"label": "01_section", "path": "../test1/01_section/1/SN002.png"}
        ]

        index_html = index_path.read_text(encoding="utf-8")
        assert "Batch Anomaly Dashboard" in index_html
        assert "SN002" in index_html
        assert "../test1/01_section/1/SN002.png" in index_html

    def test_writes_batch_length_warning(self, tmp_path):
        batch_dir = tmp_path / "batch_warning"
        reports_dir = batch_dir / "reports"
        reports_dir.mkdir(parents=True)
        write_signal_inventory(
            batch_dir / "test1" / "reports",
            [
                {
                    "serial_number": "SN003",
                    "signal_length": 22528,
                    "expected_length": 22528,
                    "length_matches_expected": True,
                }
            ],
        )
        write_signal_inventory(
            batch_dir / "test2" / "reports",
            [
                {
                    "serial_number": "SN003",
                    "signal_length": 22000,
                    "expected_length": 22528,
                    "length_matches_expected": False,
                }
            ],
        )

        generate_batch_dashboard(batch_dir, "device1", ["test1", "test2"])

        summary = json.loads((reports_dir / "summary.json").read_text(encoding="utf-8"))
        assert summary["serials"][0]["serial_number"] == "SN003"
        assert summary["serials"][0]["has_length_warning"] is True
        assert summary["serials"][0]["length_warning_tests"] == 1
        assert summary["serials"][0]["tests"][1]["has_length_warning"] is True

        index_html = (reports_dir / "index.html").read_text(encoding="utf-8")
        assert '"has_length_warning": true' in index_html.lower()
        assert '"signal_length": 22000' in index_html
        assert '"expected_length": 22528' in index_html


class TestStandaloneHtmlReports:
    """Tests for standalone Plotly HTML report generation."""

    def test_generate_html_report_uses_local_plotly_asset(self, tmp_path):
        run_dir = tmp_path / "single_run"
        _write_section_data(
            run_dir / "reports" / "section_data" / "SN010.json",
            {
                "serial_number": "SN010",
                "test_name": "test1",
                "sections": [
                    {
                        "section_name": "01_section",
                        "section_start": 0,
                        "section_end": 10,
                        "is_anomaly": True,
                        "anomaly_windows": [{"start": 2, "end": 4, "score": 0.61}],
                    }
                ],
            },
        )

        html_path = generate_html_report(
            run_dir=run_dir,
            serial_number="SN010",
            test_name="test1",
            full_signal=[0.1, 0.2, 0.3, 0.4, 0.5],
        )

        html_file = run_dir / "reports" / "html" / "SN010.html"
        asset_file = run_dir / "reports" / "html" / PLOTLY_ASSET_NAME
        assert html_path == str(html_file)
        assert asset_file.exists()

        html = html_file.read_text(encoding="utf-8")
        assert f'<script src="./{PLOTLY_ASSET_NAME}"></script>' in html
        assert "cdn.plot.ly" not in html

    def test_downsample_signal_preserves_last_point_and_positions(self):
        full_signal = list(range(MAX_PLOT_POINTS + 37))

        x_values, sampled = _downsample_signal(full_signal)

        assert x_values is not None
        assert sampled is not None
        assert len(sampled) <= MAX_PLOT_POINTS + 1
        assert x_values[-1] == len(full_signal) - 1
        assert sampled[-1] == full_signal[-1]


class TestWindowHighlighting:
    @pytest.mark.parametrize("bounds, expected", [
        ([(0, 1000), (1500, 2500)], [0, 1000, 1500, 2500]),
        ([(0, 1000), (1000, 2000)], [0, 1000, 2000]),
        ([(1500, 2500), (0, 1000)], [0, 1000, 1500, 2500]),
        ([(100, 900)], [100, 900]),
        ([], []),
    ])
    def test_section_boundaries_include_both_edges_and_deduplicate_shared_edges(self, bounds, expected):
        data = {"sections": [
            {"section_name": f"section_{index}", "section_start": start,
             "section_end": end, "is_anomaly": False, "anomaly_windows": []}
            for index, (start, end) in enumerate(bounds)
        ]}

        figure = _build_signal_figure("BOUNDARIES", "test1", data, [0.0] * 3000)

        lines = [shape for shape in figure.layout.shapes if shape.type == "line"]
        assert [line.x0 for line in lines] == expected
        assert all(line.x0 == line.x1 and line.y0 == 0 and line.y1 == 1 for line in lines)
        assert all(line.xref == "x" and line.yref == "y domain" for line in lines)
        assert len(figure.layout.annotations) == len(bounds)

    def test_fake_signal_colors_only_warning_and_error_windows(self):
        signal = [0.0] * 1200
        signal[275] = 1.0
        signal[525] = 5.0
        data = {"sections": [{
            "section_name": "synthetic_section", "section_start": 100,
            "section_end": 1100, "is_anomaly": True,
            "anomaly_windows": [
                {"start": 100, "end": 150, "score": 0.1},
                {"start": 250, "end": 300, "score": 0.355},
                {"start": 500, "end": 550, "score": 0.5},
                {"start": 800, "end": 850, "score": 0.1},
            ],
        }]}

        figure = _build_signal_figure("SYNTHETIC", "test1", data, signal)
        rectangles = [shape for shape in figure.layout.shapes if shape.type == "rect"]
        assert [(shape.x0, shape.x1) for shape in rectangles] == [(250, 300), (500, 550)]
        assert rectangles[0].fillcolor == "rgba(245, 158, 11, 0.42)"
        assert rectangles[1].fillcolor == "rgba(220, 38, 38, 0.48)"
        assert all(not (shape.x0 <= 125 < shape.x1) for shape in rectangles)
        assert all(not (shape.x0 <= 900 < shape.x1) for shape in rectangles)
        label = next(annotation for annotation in figure.layout.annotations if annotation.text == "synthetic_section")
        assert label.font.color == "#dc2626"
        assert "Status: Anomaly" in label.hovertext

    def test_normal_section_has_no_colored_rectangles(self):
        data = {"sections": [{
            "section_name": "normal_section", "section_start": 0,
            "section_end": 100, "is_anomaly": False,
            "anomaly_windows": [{"start": 0, "end": 50, "score": 0.1}],
        }]}
        figure = _build_signal_figure("NORMAL", "test1", data, [0.0] * 100)
        assert not [shape for shape in figure.layout.shapes if shape.type == "rect"]
