"""
PDF report module for anomaly detection results.

This module generates PDF reports for each serial number,
containing tables, statistics, and embedded plots.

Functions:
    generate_pdf_report: Create PDF report for a serial number
    generate_batch_pdf_reports: Create PDF reports for all serial numbers in batch mode
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether,
    LongTable
)
from reportlab.lib.enums import TA_CENTER


PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
PRIMARY_COLOR = colors.HexColor("#1f4e79")
BORDER_COLOR = colors.HexColor("#b8c7d9")
TEXT_MUTED = colors.HexColor("#4a5568")
ROW_COLORS = [colors.white, colors.HexColor("#f7fafc")]


def _build_styles() -> Dict[str, ParagraphStyle]:
    """Build shared styles for the PDF report."""
    styles = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            textColor=PRIMARY_COLOR,
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=TEXT_MUTED,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "section_title": ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=PRIMARY_COLOR,
            spaceBefore=8,
            spaceAfter=10,
        ),
        "subsection_title": ParagraphStyle(
            "SubsectionTitle",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=TEXT_MUTED,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.black,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.black,
        ),
        "table_cell_center": ParagraphStyle(
            "TableCellCenter",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            alignment=TA_CENTER,
            textColor=colors.black,
        ),
        "table_cell_status": ParagraphStyle(
            "TableCellStatus",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10.5,
            alignment=TA_CENTER,
            textColor=colors.black,
        ),
    }


PDF_STYLES = _build_styles()


def _base_table_style(header_background: colors.Color = PRIMARY_COLOR) -> TableStyle:
    """Create a consistent base table style."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_background),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.6, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), ROW_COLORS),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, PRIMARY_COLOR),
    ])


def _draw_page_frame(canvas, doc) -> None:
    """Draw a simple header and footer on each content page."""
    canvas.saveState()
    canvas.setStrokeColor(BORDER_COLOR)
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, PAGE_HEIGHT - 1.2 * cm, PAGE_WIDTH - doc.rightMargin, PAGE_HEIGHT - 1.2 * cm)
    canvas.line(doc.leftMargin, 1.1 * cm, PAGE_WIDTH - doc.rightMargin, 1.1 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(doc.leftMargin, 0.65 * cm, "Time-Series Anomaly Detection Report")
    canvas.drawRightString(PAGE_WIDTH - doc.rightMargin, 0.65 * cm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def load_section_data(run_dir: Path, serial_number: str) -> Optional[Dict[str, Any]]:
    """Load section data from JSON file."""
    section_data_file = run_dir / "reports" / "section_data" / f"{serial_number}.json"
    
    if not section_data_file.exists():
        return None
    
    with open(section_data_file, "r", encoding="utf-8") as f:
        return json.load(f)


def create_cover_page(
    serial_number: str,
    test_name: str,
    device_series: str,
    generation_date: str,
    run_mode: str,
) -> List[Any]:
    """Create cover page elements for PDF."""
    pdf_styles = PDF_STYLES
    elements = []
    info_table = Table(
        [
            [Paragraph("Device Series", pdf_styles["table_header"]), Paragraph(device_series, pdf_styles["table_cell"])],
            [Paragraph("Test Name", pdf_styles["table_header"]), Paragraph(test_name, pdf_styles["table_cell"])],
            [Paragraph("Run Mode", pdf_styles["table_header"]), Paragraph(run_mode, pdf_styles["table_cell"])],
            [Paragraph("Generated At", pdf_styles["table_header"]), Paragraph(generation_date, pdf_styles["table_cell"])],
        ],
        colWidths=[2.6 * inch, 5.4 * inch],
    )
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PRIMARY_COLOR),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.6, BORDER_COLOR),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    elements.append(Spacer(1, 2.1 * inch))
    elements.append(Paragraph("Time-Series Anomaly Detection Report", pdf_styles["cover_title"]))
    elements.append(Paragraph(f"Serial Number: {serial_number}", pdf_styles["cover_subtitle"]))
    elements.append(Spacer(1, 1.2 * inch))
    elements.append(info_table)
    return elements


def create_summary_table(sn_data: Dict[str, Any]) -> List[Any]:
    """Create executive summary table."""
    pdf_styles = PDF_STYLES
    elements = []
    elements.append(Paragraph("Executive Summary", pdf_styles["section_title"]))
    
    sections = sn_data.get("sections", [])
    total_sections = len(sections)
    anomaly_sections = sum(1 for sec in sections if sec.get("is_anomaly", False))
    normal_sections = total_sections - anomaly_sections
    
    summary_data = [
        [Paragraph("Metric", pdf_styles["table_header"]), Paragraph("Value", pdf_styles["table_header"])],
        [Paragraph("Total Sections Analyzed", pdf_styles["table_cell"]), Paragraph(str(total_sections), pdf_styles["table_cell_center"])],
        [Paragraph("Anomalous Sections", pdf_styles["table_cell"]), Paragraph(str(anomaly_sections), pdf_styles["table_cell_center"])],
        [Paragraph("Normal Sections", pdf_styles["table_cell"]), Paragraph(str(normal_sections), pdf_styles["table_cell_center"])],
        [Paragraph("Anomaly Rate", pdf_styles["table_cell"]), Paragraph(f"{(anomaly_sections / max(1, total_sections)) * 100:.1f}%", pdf_styles["table_cell_center"])],
    ]
    summary_table = Table(summary_data, colWidths=[4.6 * inch, 2.1 * inch])
    summary_table.setStyle(_base_table_style())
    elements.append(summary_table)
    return elements


def create_section_details_table(sn_data: Dict[str, Any]) -> List[Any]:
    """Create detailed section analysis table."""
    pdf_styles = PDF_STYLES
    sections = sorted(sn_data.get("sections", []), key=lambda x: x.get("section_start", 0))
    table_data = [
        [
            Paragraph("Section Name", pdf_styles["table_header"]),
            Paragraph("Position Range", pdf_styles["table_header"]),
            Paragraph("Status", pdf_styles["table_header"]),
            Paragraph("Max Score", pdf_styles["table_header"]),
        ],
    ]

    for sec in sections:
        section_name = sec.get("section_name", "N/A")
        start = sec.get("section_start", 0)
        end = sec.get("section_end", 0)
        position_range = f"{start} - {end}"
        is_anomaly = sec.get("is_anomaly", False)
        status = "Anomaly" if is_anomaly else "Normal"
        anomaly_windows = sec.get("anomaly_windows", [])
        max_score = max((w.get("score", 0) for w in anomaly_windows), default=0)

        table_data.append([
            Paragraph(section_name, pdf_styles["table_cell"]),
            Paragraph(position_range, pdf_styles["table_cell_center"]),
            Paragraph(status, pdf_styles["table_cell_status"]),
            Paragraph(f"{max_score:.4f}", pdf_styles["table_cell_center"]),
        ])

    details_table = LongTable(
        table_data,
        colWidths=[3.15 * inch, 1.75 * inch, 1.2 * inch, 1.25 * inch],
        repeatRows=1,
        splitByRow=1,
    )
    details_table.setStyle(_base_table_style())
    details_table.setStyle(TableStyle([
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (2, 1), (2, -1), PRIMARY_COLOR),
    ]))

    return [Paragraph("Section Analysis Details", pdf_styles["section_title"]), details_table]


def embed_plots(
    run_dir: Path,
    serial_number: str,
    test_name: str,
) -> List[Any]:
    """Embed PNG plots from output folders with test name labels."""
    pdf_styles = PDF_STYLES
    elements = []
    elements.append(Paragraph("Anomaly Detection Plots", pdf_styles["section_title"]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Test: {test_name}", pdf_styles["subsection_title"]))
    elements.append(Spacer(1, 0.1 * inch))
    sections_dir = run_dir
    plot_sections = []
    for section_folder in sorted(sections_dir.iterdir()):
        if not section_folder.is_dir() or section_folder.name in ["reports", "pdf_report"]:
            continue
        section_name = section_folder.name
        pos_dir = section_folder / "1"
        neg_dir = section_folder / "0"
        plot_path = pos_dir / f"{serial_number}.png"
        if not plot_path.exists():
            plot_path = neg_dir / f"{serial_number}.png"
        if plot_path.exists():
            plot_sections.append({
                "section_name": section_name,
                "plot_path": plot_path,
            })

    if not plot_sections:
        elements.append(Paragraph("This test has no detected anomalies.", pdf_styles["body"]))
        return elements

    for plot_info in plot_sections:
        section_elements = []
        section_elements.append(
            Paragraph(
                f"Section: {plot_info['section_name']}",
                pdf_styles["subsection_title"],
            )
        )
        section_elements.append(Spacer(1, 0.12 * inch))
        try:
            img = Image(str(plot_info["plot_path"]), width=7.7 * inch, height=3.85 * inch)
            section_elements.append(img)
        except Exception as e:
            section_elements.append(Paragraph(f"Could not load plot: {e}", pdf_styles["body"]))
        section_elements.append(Spacer(1, 0.3 * inch))
        elements.append(KeepTogether(section_elements))
    return elements


def _create_document(pdf_path: Path) -> SimpleDocTemplate:
    """Create a consistently configured PDF document."""
    return SimpleDocTemplate(
        str(pdf_path),
        pagesize=PAGE_SIZE,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.9 * cm,
        bottomMargin=1.6 * cm,
        title="Time-Series Anomaly Detection Report",
        author="ts-anomaly-detection",
    )


def generate_pdf_report(
    run_dir: Path,
    serial_number: str,
    test_name: str,
    device_series: str,
    threshold1: float = 0.35,
    threshold2: float = 0.36,
    run_mode: str = "Single",
) -> Optional[str]:
    """
    Generate a PDF report for a serial number.
    
    Args:
        run_dir: Output directory for this run
        serial_number: Serial number to generate report for
        test_name: Name of the test
        device_series: Device series name
        threshold1: First threshold (normal/warning)
        threshold2: Second threshold (warning/anomaly)
        run_mode: "Single" or "Batch"
        
    Returns:
        Path to generated PDF file, or None if failed
    """
    from datetime import datetime
    
    sn_data = load_section_data(run_dir, serial_number)
    
    if not sn_data:
        return None
    
    pdf_dir = run_dir / "reports" / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_path = pdf_dir / f"{serial_number}_report.pdf"
    doc = _create_document(pdf_path)
    
    elements = []
    generation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    elements.extend(create_cover_page(
        serial_number=serial_number,
        test_name=test_name,
        device_series=device_series,
        generation_date=generation_date,
        run_mode=run_mode,
    ))
    
    elements.append(PageBreak())
    
    summary_elements = create_summary_table(sn_data)
    elements.extend(summary_elements)
    elements.append(Spacer(1, 0.25 * inch))
    section_elements = create_section_details_table(sn_data)
    elements.extend(section_elements)
    plot_elements = embed_plots(run_dir, serial_number, test_name)
    if plot_elements:
        elements.append(PageBreak())
        elements.extend(plot_elements)
    doc.build(
        elements,
        onFirstPage=_draw_page_frame,
        onLaterPages=_draw_page_frame,
    )
    
    return str(pdf_path)


def generate_all_pdf_reports(
    run_dir: Path,
    test_name: str,
    device_series: str,
    threshold1: float = 0.35,
    threshold2: float = 0.36,
    run_mode: str = "Single",
) -> List[str]:
    """
    Generate PDF reports for all serial numbers.
    
    Args:
        run_dir: Output directory for this run
        test_name: Name of the test
        device_series: Device series name
        threshold1: First threshold
        threshold2: Second threshold
        run_mode: "Single" or "Batch"
        
    Returns:
        List of paths to generated PDF files
    """
    section_data_dir = run_dir / "reports" / "section_data"
    
    if not section_data_dir.exists():
        return []
    
    pdf_files = []
    
    for json_file in section_data_dir.glob("*.json"):
        serial_number = json_file.stem
        
        pdf_path = generate_pdf_report(
            run_dir=run_dir,
            serial_number=serial_number,
            test_name=test_name,
            device_series=device_series,
            threshold1=threshold1,
            threshold2=threshold2,
            run_mode=run_mode,
        )
        
        if pdf_path:
            pdf_files.append(pdf_path)
    
    return pdf_files


def generate_batch_pdf_reports(
    batch_run_dir: Path,
    device_series: str,
    test_names: List[str],
    threshold1: float = 0.35,
    threshold2: float = 0.36,
) -> List[str]:
    """
    Generate combined PDF reports for batch mode.
    Each PDF contains all tests for a single serial number.
    
    Args:
        batch_run_dir: Batch output directory
        device_series: Device series name
        test_names: List of test names in the batch
        threshold1: First threshold
        threshold2: Second threshold
        
    Returns:
        List of paths to generated PDF files
    """
    from datetime import datetime
    from collections import defaultdict
    
    all_serials = set()
    serial_test_data = defaultdict(list)
    
    for test_name in test_names:
        test_dir = batch_run_dir / test_name
        if not test_dir.exists():
            continue
        
        section_data_dir = test_dir / "reports" / "section_data"
        if not section_data_dir.exists():
            continue
        
        for json_file in section_data_dir.glob("*.json"):
            serial_number = json_file.stem
            all_serials.add(serial_number)
            serial_test_data[serial_number].append({
                "test_name": test_name,
                "run_dir": test_dir,
            })
    
    pdf_dir = batch_run_dir / "reports" / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_files = []
    
    for serial_number in sorted(all_serials):
        pdf_path = pdf_dir / f"{serial_number}_report.pdf"
        doc = _create_document(pdf_path)
        
        elements = []
        generation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        elements.extend(create_cover_page(
            serial_number=serial_number,
            test_name="All Tests (Batch)",
            device_series=device_series,
            generation_date=generation_date,
            run_mode="Batch",
        ))
        
        elements.append(PageBreak())
        
        test_data_list = serial_test_data[serial_number]
        
        for i, test_data in enumerate(test_data_list):
            test_name = test_data["test_name"]
            test_run_dir = test_data["run_dir"]
            
            sn_data = load_section_data(test_run_dir, serial_number)
            
            if sn_data:
                if i > 0:
                    elements.append(PageBreak())
                elements.append(Paragraph(f"Test: {test_name}", PDF_STYLES["section_title"]))
                elements.append(Spacer(1, 0.2 * inch))
                elements.extend(create_summary_table(sn_data))
                elements.append(Spacer(1, 0.2 * inch))
                elements.extend(create_section_details_table(sn_data))
        for test_data in serial_test_data[serial_number]:
            test_name = test_data["test_name"]
            test_run_dir = test_data["run_dir"]
            plot_elements = embed_plots(test_run_dir, serial_number, test_name)
            if plot_elements:
                elements.append(PageBreak())
                elements.extend(plot_elements)
        doc.build(
            elements,
            onFirstPage=_draw_page_frame,
            onLaterPages=_draw_page_frame,
        )
        pdf_files.append(str(pdf_path))
    
    return pdf_files
