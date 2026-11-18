"""
HTML report module for anomaly detection results.

This module generates interactive HTML reports using Plotly for each serial number,
showing all sections in a single chart with anomaly highlighting.
"""

import json
import os
import __main__
import math
import textwrap
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime
from html import escape
from pathlib import Path
from time import perf_counter
from typing import List, Dict, Any, Optional, Tuple
import plotly.graph_objects as go


HTML_TITLE_BG = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
HTML_BODY_BG = "#f4f7fb"
HTML_TEXT = "#18324b"
HTML_MUTED = "#5b6b7a"
PLOT_HEIGHT = 760
PLOTLY_ASSET_NAME = "plotly.min.js"
MAX_PLOT_POINTS = 12000
_SIGNAL_MAP_CACHE: Dict[tuple[str, str, str], Dict[str, List[float]]] = {}
NO_DATA_MESSAGE = "No data is available for this test. Model evaluation was not performed."
MISSING_TEST_MESSAGE = "This test is missing. Model evaluation was not performed."


def _no_data_html(test_name: str, missing_test: bool = False) -> str:
    """Explain an empty measurement without showing a fabricated signal."""
    title = "Missing Test" if missing_test else "No Data"
    message = MISSING_TEST_MESSAGE if missing_test else NO_DATA_MESSAGE
    sample_note = "Not evaluated." if missing_test else "Original samples: 0. Not evaluated."
    return (
        '<div role="status" style="padding:40px;max-width:800px;margin:40px auto;'
        'background:#fff1d6;color:#7c4a03;border-radius:16px;line-height:1.8">'
        f'<h2>{escape(test_name)} — {title}</h2>'
        f'<p>{message}</p>'
        f'<p>{sample_note}</p></div>'
    )


def _html_report_data(run_dir: Path, serial_number: str, test_name: str,
                      signal_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if signal_meta.get("signal_length") == 0:
        return {"serial_number": serial_number, "test_name": test_name,
                "sections": [], "has_no_data": True}
    return _load_section_data(run_dir, serial_number)


def _set_data_status(row: Dict[str, Any], signal_meta: Dict[str, Any]) -> None:
    row["is_missing_test"] = bool(signal_meta.get("missing_test", False))
    row["has_no_data"] = row["is_missing_test"] or signal_meta.get("signal_length") == 0
    row["status"] = ("missing_test" if row["is_missing_test"] else "no_data" if row["has_no_data"]
                     else "anomaly" if row["has_anomaly"] else "normal")
    if row["has_no_data"]:
        row["has_anomaly"] = False
        row["has_length_warning"] = False
        row["data_message"] = MISSING_TEST_MESSAGE if row["is_missing_test"] else NO_DATA_MESSAGE


def write_signal_inventory(reports_dir: Path, signal_inventory: List[Dict[str, Any]]) -> Path:
    """Persist per-serial signal metadata used by dashboards."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = reports_dir / "signal_inventory.json"
    with open(inventory_path, "w", encoding="utf-8") as f:
        json.dump(signal_inventory, f, indent=2, ensure_ascii=False)
    return inventory_path


def _load_signal_inventory(reports_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load per-serial signal metadata if it exists."""
    inventory_path = reports_dir / "signal_inventory.json"
    if not inventory_path.exists():
        return {}

    with open(inventory_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    inventory: Dict[str, Dict[str, Any]] = {}
    for item in payload:
        serial_number = str(item.get("serial_number", ""))
        if serial_number:
            inventory[serial_number] = item
    return inventory


def _load_section_data(run_dir: Path, serial_number: str) -> Optional[Dict[str, Any]]:
    """Load per-serial section data if it exists."""
    section_data_file = run_dir / "reports" / "section_data" / f"{serial_number}.json"
    if not section_data_file.exists():
        return None
    with open(section_data_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _default_worker_count(task_count: int) -> int:
    """Choose a conservative worker count for HTML generation."""
    if task_count <= 1:
        return 1
    cpu_count = os.cpu_count() or 1
    return max(1, min(4, cpu_count - 1, task_count))


def _load_signal_map(
    input_folder: str,
    test_name: str,
    device_series: str,
) -> Dict[str, List[float]]:
    """Load and cache full signals for HTML generation."""
    cache_key = (input_folder, test_name, device_series)
    cached = _SIGNAL_MAP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    from src.data.loader import load_valid_signals
    import gc

    signal_map: Dict[str, List[float]] = {}
    try:
        df, serial_numbers = load_valid_signals(
            input_folder=input_folder,
            test_name=test_name,
            device_series=device_series,
            report_callback=None,
            cancel_event=None
        )
        signal_map = {str(sn): df.iloc[idx]["signal"] for idx, sn in enumerate(serial_numbers)}
        del df
        gc.collect()
    except Exception:
        signal_map = {}

    _SIGNAL_MAP_CACHE[cache_key] = signal_map
    return signal_map


def _run_parallel_tasks(tasks: List[tuple], task_fn) -> List[str]:
    """Run report rendering tasks in parallel with a safe fallback."""
    worker_count = _default_worker_count(len(tasks))
    if worker_count == 1:
        return [task_fn(task) for task in tasks]

    main_file = getattr(__main__, "__file__", "")
    if not main_file or "<stdin>" in main_file:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            return list(executor.map(task_fn, tasks))

    try:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            return list(executor.map(task_fn, tasks))
    except Exception:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            return list(executor.map(task_fn, tasks))


def _ensure_plotly_asset(html_dir: Path) -> str:
    """Write a local Plotly bundle once per HTML output directory."""
    import plotly.offline as offline

    asset_path = html_dir / PLOTLY_ASSET_NAME
    if not asset_path.exists():
        asset_path.write_text(offline.get_plotlyjs(), encoding="utf-8")
    return asset_path.name


def _downsample_signal(full_signal: Optional[List[float]]) -> Tuple[Optional[List[int]], Optional[List[float]]]:
    """Reduce very large signals to keep HTML reports responsive while preserving x positions."""
    if full_signal is None:
        return None, None
    if len(full_signal) <= MAX_PLOT_POINTS:
        return list(range(len(full_signal))), full_signal

    stride = max(1, math.ceil(len(full_signal) / MAX_PLOT_POINTS))
    x_values = list(range(0, len(full_signal), stride))
    sampled = list(full_signal[::stride])
    if x_values[-1] != len(full_signal) - 1:
        x_values.append(len(full_signal) - 1)
        sampled.append(full_signal[-1])
    return x_values, sampled

def _build_signal_figure(
    serial_number: str,
    test_name: str,
    sn_data: Dict[str, Any],
    full_signal: Optional[List[float]] = None,
) -> go.Figure:
    """Build a Plotly figure for one serial number and one test."""
    sections = sorted(sn_data["sections"], key=lambda x: x["section_start"])
    fig = go.Figure()
    x_values, sampled_signal = _downsample_signal(full_signal)
    label_height = 0
    shapes = []

    if sampled_signal is not None and x_values is not None:
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=sampled_signal,
                mode="lines",
                name="Original Signal",
                line=dict(color="#1f4e79", width=1.5),
                hoverinfo="x+y+name",
            )
        )

    for sec in sections:
        is_anomaly = sec["is_anomaly"]
        # Vertical names occupy a separate band above the signal. Centering
        # each label avoids crowding names against the neighboring boundary.
        label_lines = textwrap.wrap(sec["section_name"], width=26) or [""]
        label_height = max(label_height, max(map(len, label_lines)) * 6)
        fig.add_annotation(
            x=(sec["section_start"] + sec["section_end"]) / 2,
            y=1,
            yshift=8,
            xref="x",
            yref="paper",
            text="<br>".join(escape(line) for line in label_lines),
            hovertext=(f"{escape(sec['section_name'])}<br>"
                       f"Samples: {sec['section_start']}–{sec['section_end']}<br>"
                       f"Status: {'Anomaly' if is_anomaly else 'Normal'}"),
            showarrow=False,
            textangle=-90,
            xanchor="center",
            yanchor="bottom",
            font=dict(size=10, color="#dc2626" if is_anomaly else "#1f4e79"),
        )

        for window in sec["anomaly_windows"]:
            score = window["score"]
            threshold1 = window.get("threshold1", 0.35)
            threshold2 = window.get("threshold2", 0.36)

            if score < threshold1:
                continue
            if score <= threshold2:
                win_color = "rgba(245, 158, 11, 0.42)"
            else:
                win_color = "rgba(220, 38, 38, 0.48)"

            shapes.append({
                "type": "rect", "xref": "x", "yref": "y domain",
                "x0": window["start"], "x1": window["end"], "y0": 0, "y1": 1,
                "fillcolor": win_color, "opacity": 0.5, "layer": "above",
                "line": {"width": 0},
            })

    # Draw both edges, including gaps and the outermost section boundaries.
    # Adjacent sections share one line at their common sample position.
    boundaries = sorted({
        section[edge] for section in sections
        for edge in ("section_start", "section_end")
    })
    for boundary in boundaries:
        shapes.append({
            "type": "line", "xref": "x", "yref": "y domain",
            "x0": boundary, "x1": boundary, "y0": 0, "y1": 1,
            "line": {"dash": "dash", "color": "#64748b", "width": 1},
            "opacity": 0.75, "layer": "below",
        })

    fig.update_layout(
        xaxis=dict(
            title="Time Steps (samples)",
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor="#cbd5e1",
            ticks="outside",
            tickcolor="#64748b",
            ticklen=5,
            autorange=True,
            fixedrange=False,
        ),
        yaxis=dict(
            title="Amplitude",
            showgrid=True,
            griddash="dash",
            gridcolor="lightgray",
            autorange=True,
            fixedrange=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="right",
            x=1,
        ),
        hovermode="x unified",
        template="plotly_white",
        autosize=True,
        height=PLOT_HEIGHT,
        margin=dict(l=60, r=60, t=max(130, label_height + 65), b=100),
        shapes=shapes,
        dragmode="pan",
    )
    return fig


def _plot_html(fig: go.Figure, div_id: str) -> str:
    """Serialize a Plotly figure as an embeddable HTML fragment."""
    import plotly.io as pio

    config = {
        "responsive": True,
        "scrollZoom": True,
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToAdd": [
            "drawline",
            "drawopenpath",
            "drawclosedpath",
            "drawcircle",
            "drawrect",
            "eraseshape",
        ],
        "autosizable": True,
    }
    return pio.to_html(
        fig,
        include_plotlyjs=False,
        full_html=False,
        config=config,
        div_id=div_id,
    )


def _write_single_html_report(
    run_dir_str: str,
    serial_number: str,
    test_name: str,
    sn_data: Dict[str, Any],
    full_signal: Optional[List[float]],
) -> str:
    """Render and write one single-test HTML report."""
    run_dir = Path(run_dir_str)
    html_dir = run_dir / "reports" / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    html_path = html_dir / f"{serial_number}.html"
    plotly_asset = _ensure_plotly_asset(html_dir)

    if sn_data.get("has_no_data"):
        plot_html = _no_data_html(test_name)
    else:
        fig = _build_signal_figure(serial_number, test_name, sn_data, full_signal)
        plot_html = _plot_html(fig, f"plot-{serial_number}-{test_name}")
    html_content = _single_report_html(serial_number, test_name, plot_html, plotly_asset)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return str(html_path)


def _write_batch_html_report(
    batch_run_dir_str: str,
    serial_number: str,
    device_series: str,
    test_panels: List[Dict[str, str]],
) -> str:
    """Render and write one batch HTML report."""
    batch_run_dir = Path(batch_run_dir_str)
    html_dir = batch_run_dir / "reports" / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    html_path = html_dir / f"{serial_number}.html"
    plotly_asset = _ensure_plotly_asset(html_dir)
    html_content = _batch_report_html(serial_number, device_series, test_panels, plotly_asset)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return str(html_path)


def _write_single_html_report_task(args: tuple) -> str:
    """Unpack arguments for process pool execution."""
    return _write_single_html_report(*args)


def _write_batch_html_report_task(args: tuple) -> str:
    """Unpack arguments for process pool execution."""
    return _write_batch_html_report(*args)


def _single_report_html(serial_number: str, test_name: str, plot_html: str, plotly_asset: str) -> str:
    """Build the standalone single-test HTML page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anomaly Report - {serial_number} - {test_name}</title>
    <script src="./{plotly_asset}"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
            width: 100%;
            height: 100%;
            overflow: hidden;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: {HTML_BODY_BG};
        }}
        #plot-container {{
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        #plot {{
            flex: 1;
            width: 100%;
            height: 100%;
            padding: 0;
        }}
        #plot > div {{
            width: 100%;
            height: 100%;
        }}
    </style>
</head>
<body>
    <div id="plot-container">
        <div id="plot">{plot_html}</div>
    </div>
</body>
</html>"""


def _batch_report_html(
    serial_number: str,
    device_series: str,
    test_panels: List[Dict[str, str]],
    plotly_asset: str,
) -> str:
    """Build a batch HTML report with one tab per test."""
    tabs_html = []
    panels_html = []

    for index, panel in enumerate(test_panels):
        active_class = " active" if index == 0 else ""
        hidden_attr = "" if index == 0 else " hidden"
        tabs_html.append(
            f'<button class="tab-button{active_class}" data-tab="{panel["tab_id"]}">{panel["test_name"]}</button>'
        )
        panels_html.append(
            f'''
            <section id="{panel["tab_id"]}" class="tab-panel{active_class}"{hidden_attr}>
                <div class="plot-shell">
                    {panel.get("plot_html", "")}
                    {f'<iframe class="plot-frame" src="{panel["iframe_src"]}" loading="lazy"></iframe>' if panel.get("iframe_src") else ""}
                </div>
            </section>
            '''
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batch Anomaly Report - {serial_number}</title>
    <script src="./{plotly_asset}"></script>
    <style>
        * {{
            box-sizing: border-box;
        }}
        html, body {{
            margin: 0;
            min-height: 100%;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background:
                radial-gradient(circle at top right, rgba(118, 75, 162, 0.16), transparent 28%),
                linear-gradient(180deg, #f7f9fc 0%, #edf3f9 100%);
            color: {HTML_TEXT};
        }}
        .page {{
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .hero {{
            background: {HTML_TITLE_BG};
            color: white;
            padding: 18px 24px;
            box-shadow: 0 3px 12px rgba(34, 51, 84, 0.18);
        }}
        .hero h1 {{
            margin: 0;
            font-size: 22px;
        }}
        .hero p {{
            margin: 6px 0 0;
            opacity: 0.92;
        }}
        .content {{
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            min-height: calc(100vh - 96px);
        }}
        .tabs {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .tab-button {{
            border: 0;
            border-radius: 999px;
            padding: 10px 16px;
            background: white;
            color: {HTML_MUTED};
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(31, 78, 121, 0.10);
        }}
        .tab-button.active {{
            background: #1f4e79;
            color: white;
        }}
        .tab-panel {{
            display: flex;
            flex-direction: column;
            flex: 1;
            min-height: 0;
        }}
        .tab-panel[hidden] {{
            display: none;
        }}
        .plot-shell {{
            flex: 1;
            min-height: calc(100vh - 240px);
            padding: 0;
            background: transparent;
            border-radius: 0;
            box-shadow: none;
        }}
        .plot-shell .plotly-graph-div {{
            width: 100% !important;
            height: calc(100vh - 240px) !important;
        }}
        .plot-frame {{
            width: 100%;
            height: calc(100vh - 240px);
            border: 0;
            background: transparent;
        }}
        @media (max-width: 768px) {{
            .hero {{
                padding: 16px;
            }}
            .content {{
                padding: 14px;
            }}
            .tab-button {{
                width: 100%;
                text-align: left;
            }}
            .plot-shell {{
                min-height: calc(100vh - 320px);
            }}
            .plot-shell .plotly-graph-div {{
                height: calc(100vh - 320px) !important;
            }}
            .plot-frame {{
                height: calc(100vh - 320px);
            }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <header class="hero">
            <h1>Batch Anomaly Report</h1>
            <p>Serial Number: {serial_number} | Device: {device_series}</p>
        </header>
        <main class="content">
            <nav class="tabs">
                {"".join(tabs_html)}
            </nav>
            {"".join(panels_html)}
        </main>
    </div>
    <script>
        const buttons = document.querySelectorAll('.tab-button');
        const panels = document.querySelectorAll('.tab-panel');
        buttons.forEach((button) => {{
            button.addEventListener('click', () => {{
                const targetId = button.dataset.tab;
                buttons.forEach((item) => item.classList.toggle('active', item === button));
                panels.forEach((panel) => {{
                    const isActive = panel.id === targetId;
                    panel.hidden = !isActive;
                    panel.classList.toggle('active', isActive);
                }});
                window.dispatchEvent(new Event('resize'));
            }});
        }});
    </script>
</body>
</html>"""


def save_section_data(
    run_dir: Path,
    serial_number: str,
    test_name: str,
    section_name: str,
    section_start: int,
    section_end: int,
    anomaly_windows: List[Dict[str, Any]],
    is_anomaly: bool,
) -> None:
    """
    Save section data to JSON file for later HTML report generation.
    
    Args:
        run_dir: Output directory for this run
        serial_number: Serial number of the signal
        test_name: Name of the test
        section_name: Name of the section
        section_start: Start position of this section in the full signal
        section_end: End position of this section in the full signal
        anomaly_windows: Window scores and [start, end) positions in original samples
        is_anomaly: Whether this section contains anomalies
    """
    reports_dir = run_dir / "reports" / "section_data"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    data_file = reports_dir / f"{serial_number}.json"
    
    # Load existing data or create new
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            sn_data = json.load(f)
    else:
        sn_data = {
            "serial_number": serial_number,
            "test_name": test_name,
            "sections": []
        }
    
    # Add section data
    section_data = {
        "section_name": section_name,
        "section_start": section_start,
        "section_end": section_end,
        "anomaly_windows": anomaly_windows,
        "is_anomaly": is_anomaly,
    }
    sn_data["sections"].append(section_data)
    
    # Save back
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(sn_data, f, indent=2)


def generate_html_report(
    run_dir: Path,
    serial_number: str,
    test_name: str,
    full_signal: List[float] = None,
) -> str:
    """
    Generate an interactive HTML report for a serial number.
    
    Args:
        run_dir: Output directory for this run
        serial_number: Serial number to generate report for
        test_name: Name of the test
        full_signal: Optional full signal data (if provided, use it instead of loading from sections)
        
    Returns:
        Path to generated HTML file
    """
    signal_meta = _load_signal_inventory(run_dir / "reports").get(serial_number, {})
    sn_data = _html_report_data(run_dir, serial_number, test_name, signal_meta)
    if not sn_data:
        return ""
    return _write_single_html_report(str(run_dir), serial_number, test_name, sn_data, full_signal)


def generate_all_html_reports(
    run_dir: Path,
    test_name: str,
    input_folder: str,
    device_series: str,
    signal_map: Optional[Dict[str, List[float]]] = None,
    report_callback: Optional[Any] = None,
) -> List[str]:
    """
    Generate HTML reports for all serial numbers in section_data folder.
    
    Args:
        run_dir: Output directory for this run
        test_name: Name of the test
        input_folder: Original input folder with .dat files
        device_series: Device series name
        
    Returns:
        List of paths to generated HTML files
    """
    section_data_dir = run_dir / "reports" / "section_data"
    signal_inventory = _load_signal_inventory(run_dir / "reports")
    serial_numbers = set(signal_inventory)
    serial_numbers.update(path.stem for path in section_data_dir.glob("*.json"))
    if not serial_numbers:
        return []

    timing_parts: List[str] = []
    if signal_map is None:
        start_load = perf_counter()
        signal_map = _load_signal_map(input_folder, test_name, device_series)
        timing_parts.append(f"load={perf_counter() - start_load:.2f}s")

    start_tasks = perf_counter()
    tasks = []
    for serial_number in sorted(serial_numbers):
        full_signal = signal_map.get(serial_number)
        sn_data = _html_report_data(run_dir, serial_number, test_name, signal_inventory.get(serial_number, {}))
        if sn_data:
            tasks.append((str(run_dir), serial_number, test_name, sn_data, full_signal))
    timing_parts.append(f"prepare={perf_counter() - start_tasks:.2f}s")

    if not tasks:
        if report_callback and timing_parts:
            report_callback(f"HTML timing [{test_name}]: {' | '.join(timing_parts)}")
        return []

    start_render = perf_counter()
    html_files = _run_parallel_tasks(tasks, _write_single_html_report_task)
    timing_parts.append(f"render={perf_counter() - start_render:.2f}s")
    if report_callback:
        report_callback(f"HTML timing [{test_name}]: {' | '.join(timing_parts)} | files={len(html_files)}")
    return html_files


def generate_batch_html_reports(
    batch_run_dir: Path,
    device_series: str,
    test_names: List[str],
    input_folder: str,
    signal_maps_by_test: Optional[Dict[str, Dict[str, List[float]]]] = None,
    report_callback: Optional[Any] = None,
) -> List[str]:
    """
    Generate one HTML report per serial number in batch mode.
    Each report contains tabs so the user can switch between tests.
    """
    html_dir = batch_run_dir / "reports" / "html"
    html_dir.mkdir(parents=True, exist_ok=True)

    timing_parts: List[str] = []
    signal_maps: Dict[str, Dict[str, List[float]]] = signal_maps_by_test or {}
    serials_by_test: Dict[str, set] = {}
    inventory_by_test = {}
    all_serials = set()

    start_signal_maps = perf_counter()
    for test_name in test_names:
        test_dir = batch_run_dir / test_name
        section_data_dir = test_dir / "reports" / "section_data"
        inventory_by_test[test_name] = _load_signal_inventory(test_dir / "reports")
        if not section_data_dir.exists() and not inventory_by_test[test_name]:
            continue

        json_serials = {json_file.stem for json_file in section_data_dir.glob("*.json")}
        serials_by_test[test_name] = set(json_serials)
        serials_by_test[test_name].update(inventory_by_test[test_name])
        if test_name not in signal_maps:
            signal_maps[test_name] = _load_signal_map(input_folder, test_name, device_series)
        serials_by_test[test_name].update(signal_maps[test_name].keys())

        all_serials.update(serials_by_test[test_name])
    timing_parts.append(f"signals={perf_counter() - start_signal_maps:.2f}s")

    start_tasks = perf_counter()
    tasks = []
    for serial_number in sorted(all_serials):
        test_panels = []

        for test_name in test_names:
            test_dir = batch_run_dir / test_name
            missing_test = serial_number not in serials_by_test.get(test_name, set())
            sn_data = ({"sections": [], "has_missing_test": True} if missing_test else
                       _html_report_data(test_dir, serial_number, test_name,
                                         inventory_by_test[test_name].get(serial_number, {})))
            if not sn_data:
                continue

            sections = sn_data.get("sections", [])
            tab_id = f"tab-{test_name}-{serial_number}".replace(" ", "-")
            per_test_html_path = test_dir / "reports" / "html" / f"{serial_number}.html"
            iframe_src = None
            plot_html = None

            if sn_data.get("has_missing_test"):
                plot_html = _no_data_html(test_name, missing_test=True)
            elif sn_data.get("has_no_data"):
                plot_html = _no_data_html(test_name)
            elif per_test_html_path.exists():
                iframe_src = os.path.relpath(per_test_html_path, html_dir).replace("\\", "/")
            else:
                fig = _build_signal_figure(
                    serial_number=serial_number,
                    test_name=test_name,
                    sn_data=sn_data,
                    full_signal=signal_maps.get(test_name, {}).get(serial_number),
                )
                plot_html = _plot_html(fig, f"plot-{test_name}-{serial_number}".replace(" ", "-"))

            test_panels.append({
                "tab_id": tab_id,
                "test_name": test_name,
                "plot_html": plot_html or "",
                "iframe_src": iframe_src,
                "anomaly_count": str(sum(1 for sec in sections if sec.get("is_anomaly", False))),
                "section_count": str(len(sections)),
            })

        if not test_panels:
            continue
        tasks.append((str(batch_run_dir), serial_number, device_series, test_panels))
    timing_parts.append(f"prepare={perf_counter() - start_tasks:.2f}s")

    if not tasks:
        if report_callback and timing_parts:
            report_callback(f"Batch HTML timing: {' | '.join(timing_parts)}")
        return []

    start_render = perf_counter()
    html_files = _run_parallel_tasks(tasks, _write_batch_html_report_task)
    timing_parts.append(f"render={perf_counter() - start_render:.2f}s")
    if report_callback:
        report_callback(f"Batch HTML timing: {' | '.join(timing_parts)} | files={len(html_files)}")
    return html_files


def _relative_report_path(target: Path, reports_dir: Path) -> str:
    """Build a browser-friendly relative path from reports directory to target."""
    return os.path.relpath(target, reports_dir).replace("\\", "/")


def _max_section_score(section: Dict[str, Any]) -> float:
    """Return maximum anomaly score for one section."""
    return max((float(window.get("score", 0.0)) for window in section.get("anomaly_windows", [])), default=0.0)


def _build_single_serial_summary(
    run_dir: Path,
    reports_dir: Path,
    serial_number: str,
    sn_data: Dict[str, Any],
    signal_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a summary row for one serial in single-test mode."""
    sections = sorted(sn_data.get("sections", []), key=lambda item: item.get("section_start", 0))
    anomalous_sections = [section for section in sections if section.get("is_anomaly", False)]
    html_path = run_dir / "reports" / "html" / f"{serial_number}.html"
    pdf_path = run_dir / "reports" / "pdf" / f"{serial_number}_report.pdf"
    anomaly_images = []

    for section in anomalous_sections:
        section_name = section.get("section_name", "")
        image_path = run_dir / section_name / "1" / f"{serial_number}.png"
        if image_path.exists():
            anomaly_images.append({
                "label": section_name,
                "path": _relative_report_path(image_path, reports_dir),
            })

    actual_length = signal_meta.get("signal_length") if signal_meta else None
    expected_length = signal_meta.get("expected_length") if signal_meta else None
    length_matches_expected = signal_meta.get("length_matches_expected", True) if signal_meta else True

    row = {
        "serial_number": serial_number,
        "test_name": sn_data.get("test_name", ""),
        "total_sections": len(sections),
        "anomalous_sections": len(anomalous_sections),
        "sections_with_anomaly": [section.get("section_name", "") for section in anomalous_sections],
        "has_anomaly": bool(anomalous_sections),
        "has_length_warning": not bool(length_matches_expected),
        "signal_length": actual_length,
        "expected_length": expected_length,
        "html_report_path": _relative_report_path(html_path, reports_dir) if html_path.exists() else "",
        "pdf_report_path": _relative_report_path(pdf_path, reports_dir) if pdf_path.exists() else "",
        "anomaly_images": anomaly_images,
    }
    _set_data_status(row, signal_meta or {})
    return row


def _build_batch_serial_summary(
    batch_run_dir: Path,
    reports_dir: Path,
    serial_number: str,
    test_names: List[str],
    inventory_by_test: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> Optional[Dict[str, Any]]:
    """Build one summary row for a serial in batch mode."""
    tests_summary = []

    for test_name in test_names:
        signal_meta = (inventory_by_test or {}).get(test_name, {}).get(serial_number, {})
        sn_data = _html_report_data(batch_run_dir / test_name, serial_number, test_name, signal_meta)
        if not sn_data and not signal_meta:
            signal_meta = {"missing_test": True}

        sections = sorted((sn_data or {}).get("sections", []), key=lambda item: item.get("section_start", 0))
        anomalous_sections = [section for section in sections if section.get("is_anomaly", False)]
        per_test_html = batch_run_dir / test_name / "reports" / "html" / f"{serial_number}.html"
        anomaly_images = []

        for section in anomalous_sections:
            section_name = section.get("section_name", "")
            image_path = batch_run_dir / test_name / section_name / "1" / f"{serial_number}.png"
            if image_path.exists():
                anomaly_images.append({
                    "label": section_name,
                    "path": _relative_report_path(image_path, reports_dir),
                })

        actual_length = signal_meta.get("signal_length")
        expected_length = signal_meta.get("expected_length")
        length_matches_expected = signal_meta.get("length_matches_expected", True)

        tests_summary.append({
            "test_name": test_name,
            "total_sections": len(sections),
            "anomalous_sections": len(anomalous_sections),
            "sections_with_anomaly": [section.get("section_name", "") for section in anomalous_sections],
            "has_anomaly": bool(anomalous_sections),
            "has_length_warning": not bool(length_matches_expected),
            "signal_length": actual_length,
            "expected_length": expected_length,
            "html_report_path": _relative_report_path(per_test_html, reports_dir) if per_test_html.exists() else "",
            "anomaly_images": anomaly_images,
        })
        _set_data_status(tests_summary[-1], signal_meta)

    if not tests_summary:
        return None

    tests_with_anomaly = [test for test in tests_summary if test["has_anomaly"]]
    tests_with_length_warning = [test for test in tests_summary if test.get("has_length_warning", False)]
    no_data_tests = sum(test["has_no_data"] for test in tests_summary)
    status = ("no_data" if no_data_tests == len(tests_summary) else
              "anomaly" if tests_with_anomaly else "incomplete" if no_data_tests else "normal")
    batch_html_path = batch_run_dir / "reports" / "html" / f"{serial_number}.html"
    batch_pdf_path = batch_run_dir / "reports" / "pdf" / f"{serial_number}_report.pdf"

    return {
        "serial_number": serial_number,
        "tests": tests_summary,
        "test_count": len(tests_summary),
        "anomalous_tests": len(tests_with_anomaly),
        "length_warning_tests": len(tests_with_length_warning),
        "has_anomaly": bool(tests_with_anomaly),
        "has_length_warning": bool(tests_with_length_warning),
        "has_no_data": bool(no_data_tests),
        "no_data_tests": no_data_tests,
        "evaluated_tests": len(tests_summary) - no_data_tests,
        "missing_tests": [test["test_name"] for test in tests_summary if test["is_missing_test"]],
        "status": status,
        "html_report_path": _relative_report_path(batch_html_path, reports_dir) if batch_html_path.exists() else "",
        "pdf_report_path": _relative_report_path(batch_pdf_path, reports_dir) if batch_pdf_path.exists() else "",
    }


def _sort_summary_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort serial summaries by serial number for the default dashboard order."""
    return sorted(rows, key=lambda item: item.get("serial_number", ""))


def _dashboard_html(summary: Dict[str, Any]) -> str:
    """Build the main dashboard HTML page."""
    serialized_summary = json.dumps(summary, ensure_ascii=False)
    title = "Batch Anomaly Dashboard" if summary.get("run_mode") == "batch" else "Anomaly Dashboard"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(title)}</title>
    <style>
        :root {{
            --bg: #eef3f8;
            --surface: #ffffff;
            --surface-strong: #0f2740;
            --text: #18324b;
            --muted: #617487;
            --accent: #1f4e79;
            --accent-soft: #d9e7f5;
            --danger: #c62828;
            --danger-soft: #fde8e8;
            --success: #137a4f;
            --success-soft: #e3f5ec;
            --warning: #b97300;
            --warning-soft: #fff1d6;
            --border: #d7e2ee;
            --shadow: 0 18px 45px rgba(21, 49, 78, 0.08);
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at top left, rgba(31, 78, 121, 0.12), transparent 28%),
                linear-gradient(180deg, #f5f8fb 0%, var(--bg) 100%);
        }}
        .page {{
            max-width: 1440px;
            margin: 0 auto;
            padding: 28px;
        }}
        .hero {{
            background: linear-gradient(135deg, #163452 0%, #245d91 100%);
            color: white;
            border-radius: 24px;
            padding: 28px;
            box-shadow: var(--shadow);
        }}
        .hero h1 {{
            margin: 0;
            font-size: 30px;
        }}
        .hero p {{
            margin: 10px 0 0;
            color: rgba(255, 255, 255, 0.84);
        }}
        .meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 18px;
        }}
        .meta-chip {{
            padding: 9px 14px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.16);
            font-size: 14px;
        }}
        .controls {{
            margin-top: 22px;
            background: var(--surface);
            border-radius: 20px;
            padding: 18px;
            box-shadow: var(--shadow);
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
        }}
        .controls input,
        .controls select {{
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 10px 12px;
            font-size: 14px;
            background: #f8fbfe;
            color: var(--text);
        }}
        .controls input {{
            min-width: 260px;
            flex: 1;
        }}
        .table-wrap {{
            margin-top: 22px;
            background: var(--surface);
            border-radius: 20px;
            box-shadow: var(--shadow);
            overflow: hidden;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        thead {{
            background: #f3f7fb;
        }}
        th, td {{
            padding: 15px 16px;
            border-bottom: 1px solid var(--border);
            vertical-align: top;
            text-align: left;
        }}
        th {{
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            color: var(--muted);
        }}
        tr:hover {{
            background: #fafcff;
        }}
        .status {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 7px 12px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 600;
        }}
        .status.anomaly {{
            color: var(--danger);
            background: var(--danger-soft);
        }}
        .status.normal {{
            color: var(--success);
            background: var(--success-soft);
        }}
        .status.no_data, .status.incomplete {{
            color: var(--warning);
            background: var(--warning-soft);
        }}
        .badge-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            border-radius: 999px;
            background: var(--accent-soft);
            color: var(--accent);
            font-size: 12px;
            font-weight: 600;
        }}
        .badge.warn {{
            background: var(--warning-soft);
            color: var(--warning);
        }}
        .badge.alert {{
            background: #fff4e5;
            color: #b45309;
        }}
        .actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .actions a {{
            text-decoration: none;
            color: white;
            background: var(--accent);
            padding: 9px 12px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
        }}
        .actions a.secondary {{
            color: var(--accent);
            background: var(--accent-soft);
        }}
        .actions a.danger {{
            color: white;
            background: var(--danger);
        }}
        .actions a[data-image-link="true"] {{
            font-size: 11px;
            padding: 7px 10px;
        }}
        .actions a.reviewed {{
            color: #5c6773;
            background: #e6ebf1;
            border: 1px solid #c8d1dc;
        }}
        .empty {{
            padding: 28px;
            color: var(--muted);
            text-align: center;
        }}
        @media (max-width: 900px) {{
            .page {{
                padding: 16px;
            }}
            .hero {{
                padding: 22px;
            }}
            th:nth-child(3),
            td:nth-child(3) {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <section class="hero">
            <h1>{escape(title)}</h1>
            <p>Centralized anomaly review for this pipeline run.</p>
            <div class="meta">
                <span class="meta-chip">Device: {escape(summary.get("device_series", ""))}</span>
                <span class="meta-chip">Mode: {escape(summary.get("run_mode", ""))}</span>
                <span class="meta-chip">Serials: <strong id="total-serials">{summary.get("totals", {}).get("total_serials", 0)}</strong></span>
                <span class="meta-chip">Generated: {escape(summary.get("generated_at", ""))}</span>
            </div>
        </section>
        <section class="controls">
            <input id="search" type="search" placeholder="Search by serial number, section, or test">
            <select id="status-filter">
                <option value="all">All statuses</option>
                <option value="anomaly">Only anomaly</option>
                <option value="normal">Only normal</option>
                <option value="no_data">Missing test data</option>
            </select>
            <select id="test-filter">
                <option value="all">All tests</option>
            </select>
            <select id="sort-filter">
                <option value="serial">Sort by serial</option>
                <option value="severity">Sort by severity</option>
            </select>
        </section>
        <section class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Serial</th>
                        <th>Status</th>
                        <th>Coverage</th>
                        <th>Highlights</th>
                        <th>Reports</th>
                        <th>Images</th>
                    </tr>
                </thead>
                <tbody id="rows"></tbody>
            </table>
            <div id="empty" class="empty" hidden>No rows match the current filters.</div>
        </section>
    </div>
    <script>
        const summary = {serialized_summary};
        const rowsHost = document.getElementById('rows');
        const emptyState = document.getElementById('empty');
        const searchInput = document.getElementById('search');
        const statusFilter = document.getElementById('status-filter');
        const testFilter = document.getElementById('test-filter');
        const sortFilter = document.getElementById('sort-filter');
        const dashboardScope = window.location.pathname || 'dashboard';
        const reviewedStorageKey = `anomaly-dashboard-reviewed:${{dashboardScope}}`;

        const loadReviewedLinks = () => {{
            try {{
                const value = localStorage.getItem(reviewedStorageKey);
                const parsed = value ? JSON.parse(value) : [];
                return new Set(Array.isArray(parsed) ? parsed : []);
            }} catch (_error) {{
                return new Set();
            }}
        }};

        const saveReviewedLinks = (reviewedLinks) => {{
            try {{
                localStorage.setItem(reviewedStorageKey, JSON.stringify([...reviewedLinks]));
            }} catch (_error) {{
                // Ignore storage failures and keep the dashboard usable.
            }}
        }};

        const reviewedLinks = loadReviewedLinks();

        const testNames = summary.run_mode === 'batch'
            ? [...new Set(summary.serials.flatMap((item) => item.tests.map((test) => test.test_name)))]
            : [...new Set(summary.serials.map((item) => item.test_name).filter(Boolean))];

        testNames.forEach((name) => {{
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            testFilter.appendChild(option);
        }});

        const statusMarkup = (item) => {{
            if (item.status === 'no_data') return '<span class="status no_data">No Data — Not evaluated</span>';
            if (item.status === 'incomplete') return '<span class="status incomplete">Incomplete — Missing test data</span>';
            return item.has_anomaly
                ? '<span class="status anomaly">Anomaly</span>'
                : '<span class="status normal">Normal</span>';
        }};

        const escapeHtml = (value) => String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');

        const highlightsMarkup = (item) => {{
            if (summary.run_mode === 'batch') {{
                return item.tests.map((test) => {{
                    const badges = [];
                    if (test.is_missing_test) {{
                        return `<span class="badge alert">${{escapeHtml(test.test_name)}}: Missing</span>`;
                    }}
                    if (test.has_no_data) {{
                        return `<span class="badge alert">${{escapeHtml(test.test_name)}}: No Data</span>`;
                    }}
                    if (test.has_length_warning) {{
                        badges.push(
                            `<span class="badge alert">${{escapeHtml(`${{test.test_name}}: length ${{test.signal_length}} / ${{test.expected_length}}`)}}</span>`
                        );
                    }}
                    const kind = test.has_anomaly ? 'warn' : '';
                    const label = `${{test.test_name}}: ${{test.anomalous_sections}}/${{test.total_sections}}`;
                    badges.push(`<span class="badge ${{kind}}">${{escapeHtml(label)}}</span>`);
                    return badges.join('');
                }}).join('');
            }}

            if (item.has_no_data) {{
                return '<span class="badge alert">No Data</span>';
            }}
            if (item.has_length_warning) {{
                return `<span class="badge alert">${{escapeHtml(`Length: ${{item.signal_length}} / ${{item.expected_length}}`)}}</span>`;
            }}

            if (!item.sections_with_anomaly.length) {{
                return '<span class="badge">No anomalies</span>';
            }}

            return item.sections_with_anomaly
                .map((name) => `<span class="badge warn">${{escapeHtml(name)}}</span>`)
                .join('');
        }};

        const coverageMarkup = (item) => {{
            if (item.status === 'no_data') return 'Not evaluated';
            if (summary.run_mode === 'batch') {{
                return `${{item.evaluated_tests}}/${{item.test_count}} evaluated tests`;
            }}
            return `${{item.anomalous_sections}}/${{item.total_sections}} sections`;
        }};

        const reportsMarkup = (item) => {{
            const links = [];
            if (item.html_report_path) {{
                links.push(`<a href="${{escapeHtml(item.html_report_path)}}" target="_blank" rel="noopener noreferrer">Open HTML</a>`);
            }}
            if (item.pdf_report_path) {{
                links.push(`<a href="${{escapeHtml(item.pdf_report_path)}}" class="secondary" target="_blank" rel="noopener noreferrer">Open PDF</a>`);
            }}
            if (summary.run_mode === 'batch') {{
                item.tests.forEach((test) => {{
                    if (test.html_report_path) {{
                        const cssClass = test.has_anomaly ? 'danger' : 'secondary';
                        links.push(`<a href="${{escapeHtml(test.html_report_path)}}" class="${{cssClass}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(test.test_name)}}</a>`);
                    }}
                }});
            }}
            return links.length ? links.join('') : '<span class="badge">No reports</span>';
        }};

        const imagesMarkup = (item) => {{
            const links = [];
            if (summary.run_mode === 'batch') {{
                item.tests.forEach((test) => {{
                    (test.anomaly_images || []).forEach((image) => {{
                        const reviewedClass = reviewedLinks.has(image.path) ? ' reviewed' : '';
                        links.push(`<a href="${{escapeHtml(image.path)}}" class="danger${{reviewedClass}}" data-image-link="true" data-image-path="${{escapeHtml(image.path)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(test.test_name + '/' + image.label)}}</a>`);
                    }});
                }});
            }} else {{
                (item.anomaly_images || []).forEach((image) => {{
                    const reviewedClass = reviewedLinks.has(image.path) ? ' reviewed' : '';
                    links.push(`<a href="${{escapeHtml(image.path)}}" class="danger${{reviewedClass}}" data-image-link="true" data-image-path="${{escapeHtml(image.path)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.test_name + '/' + image.label)}}</a>`);
                }});
            }}
            return links.length ? links.join('') : '<span class="badge">No images</span>';
        }};

        const matchesSearch = (item, query) => {{
            if (!query) {{
                return true;
            }}
            const haystack = [
                item.serial_number,
                item.test_name || '',
                ...(item.sections_with_anomaly || []),
                ...((item.tests || []).flatMap((test) => [test.test_name, ...(test.sections_with_anomaly || [])])),
            ].join(' ').toLowerCase();
            return haystack.includes(query);
        }};

        const matchesTest = (item, selectedTest) => {{
            if (selectedTest === 'all') {{
                return true;
            }}
            if (summary.run_mode === 'batch') {{
                return item.tests.some((test) => test.test_name === selectedTest);
            }}
            return item.test_name === selectedTest;
        }};

        const render = () => {{
            const query = searchInput.value.trim().toLowerCase();
            const selectedStatus = statusFilter.value;
            const selectedTest = testFilter.value;
            const sortMode = sortFilter.value;

            let items = summary.serials.filter((item) => {{
                if (selectedStatus === 'anomaly' && !item.has_anomaly) {{
                    return false;
                }}
                if (selectedStatus === 'normal' && item.status !== 'normal') {{
                    return false;
                }}
                if (selectedStatus === 'no_data' && !item.has_no_data) {{
                    return false;
                }}
                if (!matchesTest(item, selectedTest)) {{
                    return false;
                }}
                return matchesSearch(item, query);
            }});

            if (sortMode === 'serial') {{
                items = [...items].sort((a, b) => a.serial_number.localeCompare(b.serial_number));
            }} else {{
                items = [...items].sort((a, b) => {{
                    const anomalyDelta = Number(b.has_anomaly) - Number(a.has_anomaly);
                    if (anomalyDelta !== 0) {{
                        return anomalyDelta;
                    }}

                    const aCount = Number(a.anomalous_sections ?? a.anomalous_tests ?? 0);
                    const bCount = Number(b.anomalous_sections ?? b.anomalous_tests ?? 0);
                    if (bCount !== aCount) {{
                        return bCount - aCount;
                    }}

                    return a.serial_number.localeCompare(b.serial_number);
                }});
            }}

            rowsHost.innerHTML = items.map((item) => `
                <tr>
                    <td><strong>${{escapeHtml(item.serial_number)}}</strong></td>
                    <td>${{statusMarkup(item)}}</td>
                    <td>${{escapeHtml(coverageMarkup(item))}}</td>
                    <td><div class="badge-row">${{highlightsMarkup(item)}}</div></td>
                    <td><div class="actions">${{reportsMarkup(item)}}</div></td>
                    <td><div class="actions">${{imagesMarkup(item)}}</div></td>
                </tr>
            `).join('');

            const hasRows = items.length > 0;
            emptyState.hidden = hasRows;
            rowsHost.parentElement.hidden = !hasRows;
            rowsHost.querySelectorAll('[data-image-link="true"]').forEach((link) => {{
                link.addEventListener('click', () => {{
                    const imagePath = link.dataset.imagePath;
                    if (!imagePath) {{
                        return;
                    }}
                    reviewedLinks.add(imagePath);
                    saveReviewedLinks(reviewedLinks);
                    link.classList.add('reviewed');
                }});
            }});
        }};

        [searchInput, statusFilter, testFilter, sortFilter].forEach((element) => {{
            element.addEventListener('input', render);
            element.addEventListener('change', render);
        }});

        render();
    </script>
</body>
</html>"""


def generate_run_dashboard(
    run_dir: Path,
    device_series: str,
    test_name: str,
) -> Dict[str, str]:
    """Generate summary.json and index.html for a single-test run."""
    reports_dir = run_dir / "reports"
    section_data_dir = reports_dir / "section_data"
    reports_dir.mkdir(parents=True, exist_ok=True)
    signal_inventory = _load_signal_inventory(reports_dir)

    serials = []
    serial_numbers = set(signal_inventory.keys())
    if section_data_dir.exists():
        serial_numbers.update(json_file.stem for json_file in sorted(section_data_dir.glob("*.json")))

    for serial_number in sorted(serial_numbers):
        sn_data = _html_report_data(run_dir, serial_number, test_name,
                                    signal_inventory.get(serial_number, {}))
        if sn_data:
            serials.append(
                _build_single_serial_summary(
                    run_dir,
                    reports_dir,
                    serial_number,
                    sn_data,
                    signal_inventory.get(serial_number),
                )
            )
        elif serial_number in signal_inventory:
            serials.append(
                {
                    "serial_number": serial_number,
                    "test_name": test_name,
                    "total_sections": 0,
                    "anomalous_sections": 0,
                    "sections_with_anomaly": [],
                    "has_anomaly": False,
                    "has_length_warning": not bool(signal_inventory[serial_number].get("length_matches_expected", True)),
                    "signal_length": signal_inventory[serial_number].get("signal_length"),
                    "expected_length": signal_inventory[serial_number].get("expected_length"),
                    "html_report_path": "",
                    "pdf_report_path": "",
                    "anomaly_images": [],
                }
            )
            _set_data_status(serials[-1], signal_inventory[serial_number])

    serials = _sort_summary_rows(serials)
    anomaly_count = sum(1 for item in serials if item.get("has_anomaly", False))
    summary = {
        "run_mode": "single",
        "device_series": device_series,
        "test_name": test_name,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "totals": {
            "total_serials": len(serials),
            "anomalous_serials": anomaly_count,
            "normal_serials": sum(item["status"] == "normal" for item in serials),
            "serials_with_no_data": sum(item["has_no_data"] for item in serials),
            "no_data_serials": sum(item["status"] == "no_data" for item in serials),
            "total_anomalous_sections": sum(int(item.get("anomalous_sections", 0)) for item in serials),
        },
        "serials": serials,
    }

    summary_path = reports_dir / "summary.json"
    index_path = reports_dir / "index.html"
    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)
    with open(index_path, "w", encoding="utf-8") as file:
        file.write(_dashboard_html(summary))

    return {
        "summary_path": str(summary_path),
        "index_path": str(index_path),
    }


def generate_batch_dashboard(
    batch_run_dir: Path,
    device_series: str,
    test_names: List[str],
) -> Dict[str, str]:
    """Generate summary.json and index.html for a batch run."""
    reports_dir = batch_run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    serial_numbers = set()
    inventory_by_test: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for test_name in test_names:
        test_reports_dir = batch_run_dir / test_name / "reports"
        inventory_by_test[test_name] = _load_signal_inventory(test_reports_dir)
        serial_numbers.update(inventory_by_test[test_name].keys())
        section_data_dir = batch_run_dir / test_name / "reports" / "section_data"
        if not section_data_dir.exists():
            continue
        serial_numbers.update(json_file.stem for json_file in section_data_dir.glob("*.json"))

    serials = []
    for serial_number in sorted(serial_numbers):
        summary_row = _build_batch_serial_summary(
            batch_run_dir,
            reports_dir,
            serial_number,
            test_names,
            inventory_by_test,
        )
        if summary_row:
            serials.append(summary_row)

    serials = _sort_summary_rows(serials)
    anomaly_count = sum(1 for item in serials if item.get("has_anomaly", False))
    summary = {
        "run_mode": "batch",
        "device_series": device_series,
        "test_names": test_names,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "totals": {
            "total_serials": len(serials),
            "anomalous_serials": anomaly_count,
            "normal_serials": sum(item["status"] == "normal" for item in serials),
            "serials_with_no_data": sum(item["has_no_data"] for item in serials),
            "no_data_serials": sum(item["status"] == "no_data" for item in serials),
            "incomplete_serials": sum(item["status"] == "incomplete" for item in serials),
            "tests_without_data": sum(item["no_data_tests"] for item in serials),
            "total_tests": len(test_names),
        },
        "serials": serials,
    }

    summary_path = reports_dir / "summary.json"
    index_path = reports_dir / "index.html"
    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)
    with open(index_path, "w", encoding="utf-8") as file:
        file.write(_dashboard_html(summary))

    return {
        "summary_path": str(summary_path),
        "index_path": str(index_path),
    }
