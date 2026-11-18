"""
Graphical user interface for time series anomaly detection system.

This module provides a Tkinter application that allows users to:
- Select data folder
- Choose device and test name
- Run anomaly detection process and monitor progress
- Cancel operations

Classes:
    FolderPickerApp: Main application with complete GUI
"""

import json
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

from src.config import global_config as CFG
from src.pipeline.runner import UserConfig, run_all_tests_for_device, run_anomaly_detection
from src.version import __version__


class ThresholdEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.title("Threshold Configuration")
        self.geometry("1160x720")
        self.minsize(980, 620)
        self.transient(master)
        self.configure(bg="#e9eef5")

        self.device_var = tk.StringVar()
        self.test_var = tk.StringVar()
        self.section_var = tk.StringVar()
        self.threshold1_var = tk.StringVar()
        self.threshold2_var = tk.StringVar()
        self.summary_var = tk.StringVar(value="Select a section to edit its thresholds.")
        self.save_status_var = tk.StringVar(
            value="Default values come from global_config.py. Changes here apply only to this app session."
        )
        self.reset_button_var = tk.StringVar(value="Reset Selected Section")

        self.device_list: tk.Listbox | None = None
        self.test_list: tk.Listbox | None = None
        self.section_tree: ttk.Treeview | None = None
        self._config_snapshot: dict[str, dict[str, dict]] = {}
        self._default_snapshot: dict[str, dict[str, dict]] = {}
        self._selected_section_key: tuple[str, str, str] | None = None

        self._refresh_snapshots()
        self._build_ui()
        self._populate_devices()
        self.grab_set()

    def _refresh_snapshots(self) -> None:
        self._default_snapshot = CFG.get_config_snapshot(apply_threshold_overrides=False)
        self._config_snapshot = CFG.get_config_snapshot(apply_threshold_overrides=True)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=18)
        root.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        header = ttk.Frame(root, style="Hero.TFrame", padding=(24, 18))
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.grid_columnconfigure(0, weight=1)
        ttk.Label(header, text="Threshold Configuration", style="HeroTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Browse devices, tests, and sections in config order. Edit threshold1 and threshold2 for the selected section.",
            style="HeroSub.TLabel",
            wraplength=820,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(header, textvariable=self.save_status_var, style="HeroSub.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")

        content = ttk.Frame(root, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=0, minsize=220)
        content.grid_columnconfigure(1, weight=0, minsize=220)
        content.grid_columnconfigure(2, weight=1)
        content.grid_rowconfigure(0, weight=1)

        device_card = ttk.LabelFrame(content, text="Devices", padding=12)
        device_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        device_card.grid_columnconfigure(0, weight=1)
        device_card.grid_rowconfigure(0, weight=1)

        test_card = ttk.LabelFrame(content, text="Tests", padding=12)
        test_card.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        test_card.grid_columnconfigure(0, weight=1)
        test_card.grid_rowconfigure(0, weight=1)

        details_card = ttk.LabelFrame(content, text="Sections", padding=12)
        details_card.grid(row=0, column=2, sticky="nsew")
        details_card.grid_columnconfigure(0, weight=1)
        details_card.grid_rowconfigure(0, weight=1)
        details_card.grid_rowconfigure(1, weight=0)

        self.device_list = tk.Listbox(
            device_card,
            exportselection=False,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg="#f8fafc",
            fg="#17324d",
            activestyle="none",
            selectbackground="#1f4e79",
            selectforeground="#ffffff",
            font=("Segoe UI", 10),
        )
        self.device_list.grid(row=0, column=0, sticky="nsew")
        self.device_list.bind("<<ListboxSelect>>", self._on_device_selected)

        device_scroll = ttk.Scrollbar(device_card, orient="vertical", command=self.device_list.yview)
        device_scroll.grid(row=0, column=1, sticky="ns")
        self.device_list.configure(yscrollcommand=device_scroll.set)

        self.test_list = tk.Listbox(
            test_card,
            exportselection=False,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg="#f8fafc",
            fg="#17324d",
            activestyle="none",
            selectbackground="#1f4e79",
            selectforeground="#ffffff",
            font=("Segoe UI", 10),
        )
        self.test_list.grid(row=0, column=0, sticky="nsew")
        self.test_list.bind("<<ListboxSelect>>", self._on_test_selected)

        test_scroll = ttk.Scrollbar(test_card, orient="vertical", command=self.test_list.yview)
        test_scroll.grid(row=0, column=1, sticky="ns")
        self.test_list.configure(yscrollcommand=test_scroll.set)

        self.section_tree = ttk.Treeview(
            details_card,
            columns=("threshold1", "threshold2", "mode"),
            show="tree headings",
            selectmode="browse",
            height=16,
        )
        self.section_tree.heading("#0", text="Section")
        self.section_tree.heading("threshold1", text="Threshold 1")
        self.section_tree.heading("threshold2", text="Threshold 2")
        self.section_tree.heading("mode", text="Mode")
        self.section_tree.column("#0", width=260, anchor="w")
        self.section_tree.column("threshold1", width=120, anchor="center")
        self.section_tree.column("threshold2", width=120, anchor="center")
        self.section_tree.column("mode", width=120, anchor="center")
        self.section_tree.grid(row=0, column=0, sticky="nsew")
        self.section_tree.bind("<<TreeviewSelect>>", self._on_section_selected)

        section_scroll = ttk.Scrollbar(details_card, orient="vertical", command=self.section_tree.yview)
        section_scroll.grid(row=0, column=1, sticky="ns")
        self.section_tree.configure(yscrollcommand=section_scroll.set)

        editor = ttk.Frame(details_card, style="Card.TFrame")
        editor.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        editor.grid_columnconfigure(1, weight=1)
        editor.grid_columnconfigure(3, weight=1)

        ttk.Label(editor, textvariable=self.summary_var, style="Muted.TLabel", wraplength=560, justify="left").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10)
        )
        ttk.Label(editor, text="Threshold 1").grid(row=1, column=0, sticky="w", pady=(0, 10))
        ttk.Entry(editor, textvariable=self.threshold1_var).grid(row=1, column=1, sticky="ew", padx=(10, 16), pady=(0, 10))
        ttk.Label(editor, text="Threshold 2").grid(row=1, column=2, sticky="w", pady=(0, 10))
        ttk.Entry(editor, textvariable=self.threshold2_var).grid(row=1, column=3, sticky="ew", padx=(10, 0), pady=(0, 10))

        actions = ttk.Frame(editor, style="Card.TFrame")
        actions.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        actions.grid_columnconfigure(2, weight=1)

        ttk.Button(actions, textvariable=self.reset_button_var, style="Secondary.TButton", command=self._reset_selected_to_default).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(actions, text="Apply", style="Primary.TButton", command=self._apply_thresholds).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        ttk.Button(actions, text="Close", style="Secondary.TButton", command=self.destroy).grid(
            row=0, column=2, sticky="ew", padx=(8, 0)
        )

    def _populate_devices(self) -> None:
        if self.device_list is None:
            return
        self.device_list.delete(0, tk.END)
        devices = list(self._config_snapshot.keys())
        for device_name in devices:
            self.device_list.insert(tk.END, device_name)
        if devices:
            self.device_list.selection_set(0)
            self.device_list.activate(0)
            self._on_device_selected()

    def _populate_tests(self, device_name: str) -> None:
        if self.test_list is None:
            return
        self.test_list.delete(0, tk.END)
        tests = list(self._config_snapshot.get(device_name, {}).keys())
        for test_name in tests:
            self.test_list.insert(tk.END, test_name)
        if tests:
            self.test_list.selection_set(0)
            self.test_list.activate(0)
            self._on_test_selected()
        else:
            self._clear_sections()

    def _populate_sections(self, device_name: str, test_name: str) -> None:
        if self.section_tree is None:
            return
        self._clear_sections()
        ordered_sections = CFG.get_sections_order(device_name, test_name)
        sections = self._config_snapshot.get(device_name, {}).get(test_name, {}).get("sections", {})
        for section_name in ordered_sections:
            section_cfg = sections.get(section_name, {})
            is_override = CFG.has_threshold_override(device_name, test_name, section_name)
            self.section_tree.insert(
                "",
                "end",
                iid=section_name,
                text=section_name,
                values=(
                    str(section_cfg.get("threshold1", "")),
                    str(section_cfg.get("threshold2", "")),
                    "Override" if is_override else "Default",
                ),
            )
        if ordered_sections:
            first_section = ordered_sections[0]
            self.section_tree.selection_set(first_section)
            self.section_tree.focus(first_section)
            self._on_section_selected()

    def _clear_sections(self) -> None:
        if self.section_tree is not None:
            for item_id in self.section_tree.get_children():
                self.section_tree.delete(item_id)
        self._selected_section_key = None
        self.threshold1_var.set("")
        self.threshold2_var.set("")
        self.summary_var.set("Select a section to edit its thresholds.")
        self.reset_button_var.set("Reset Selected Section")

    def _get_selected_listbox_value(self, listbox: tk.Listbox | None) -> str:
        if listbox is None:
            return ""
        selection = listbox.curselection()
        if not selection:
            return ""
        return str(listbox.get(selection[0]))

    def _on_device_selected(self, _event=None) -> None:
        device_name = self._get_selected_listbox_value(self.device_list)
        self.device_var.set(device_name)
        if device_name:
            self._populate_tests(device_name)
        else:
            self._clear_sections()

    def _on_test_selected(self, _event=None) -> None:
        device_name = self._get_selected_listbox_value(self.device_list)
        test_name = self._get_selected_listbox_value(self.test_list)
        self.test_var.set(test_name)
        if device_name and test_name:
            self._populate_sections(device_name, test_name)
        else:
            self._clear_sections()

    def _on_section_selected(self, _event=None) -> None:
        if self.section_tree is None:
            return
        selection = self.section_tree.selection()
        if not selection:
            return

        section_name = selection[0]
        device_name = self._get_selected_listbox_value(self.device_list)
        test_name = self._get_selected_listbox_value(self.test_list)
        section_cfg = self._config_snapshot.get(device_name, {}).get(test_name, {}).get("sections", {}).get(section_name, {})
        self.section_var.set(section_name)
        self.threshold1_var.set(str(section_cfg.get("threshold1", "")))
        self.threshold2_var.set(str(section_cfg.get("threshold2", "")))
        is_override = CFG.has_threshold_override(device_name, test_name, section_name)
        suffix = " | runtime override active" if is_override else " | using defaults"
        self.summary_var.set(f"Editing {device_name} / {test_name} / {section_name}{suffix}")
        self.reset_button_var.set(f"Reset {section_name} to Default")
        self._selected_section_key = (device_name, test_name, section_name)

    def _reset_selected_to_default(self) -> None:
        if not self._selected_section_key:
            messagebox.showwarning("Warning", "Select a section first.", parent=self)
            return

        device_name, test_name, section_name = self._selected_section_key
        CFG.clear_threshold_override(device_name, test_name, section_name)
        self._refresh_snapshots()
        self._populate_devices()
        self._restore_selection((device_name, test_name, section_name))
        self.save_status_var.set(
            f"Reset to defaults from global_config.py for {device_name} / {test_name} / {section_name}."
        )

    def _restore_selection(self, selection_key: tuple[str, str, str]) -> None:
        device_name, test_name, section_name = selection_key
        if self.device_list is None or self.test_list is None or self.section_tree is None:
            return

        devices = list(self._config_snapshot.keys())
        if device_name not in devices:
            return
        device_index = devices.index(device_name)
        self.device_list.selection_clear(0, tk.END)
        self.device_list.selection_set(device_index)
        self.device_list.activate(device_index)
        self._on_device_selected()

        tests = list(self._config_snapshot.get(device_name, {}).keys())
        if test_name not in tests:
            return
        test_index = tests.index(test_name)
        self.test_list.selection_clear(0, tk.END)
        self.test_list.selection_set(test_index)
        self.test_list.activate(test_index)
        self._on_test_selected()

        if section_name in self.section_tree.get_children():
            self.section_tree.selection_set(section_name)
            self.section_tree.focus(section_name)
            self._on_section_selected()

    def _apply_thresholds(self) -> None:
        if not self._selected_section_key:
            messagebox.showwarning("Warning", "Select a section first.", parent=self)
            return

        try:
            threshold1 = float(self.threshold1_var.get().strip())
            threshold2 = float(self.threshold2_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Threshold values must be numeric.", parent=self)
            return

        device_name, test_name, section_name = self._selected_section_key
        CFG.set_threshold_override(device_name, test_name, section_name, threshold1, threshold2)
        self._refresh_snapshots()

        if self.section_tree is not None:
            self.section_tree.item(section_name, values=(str(threshold1), str(threshold2), "Override"))
        self._on_section_selected()
        self.save_status_var.set(
            f"Applied runtime override for {device_name} / {test_name} / {section_name}. global_config.py was not modified."
        )


class FolderPickerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"Time Series Anomaly Detection — v{__version__}")
        self.geometry("1180x760")
        self.minsize(960, 640)
        self.resizable(True, True)
        self.configure(bg="#e9eef5")

        self.selected_folder = tk.StringVar(value="")
        self.device_series = tk.StringVar(value=CFG.DEFAULT_DEVICE)
        initial_tests = CFG.get_tests_for_device(CFG.DEFAULT_DEVICE)
        self.test_name = tk.StringVar(value=(initial_tests[0] if initial_tests else ""))

        self.create_plot = tk.BooleanVar(value=False)
        self.batch_mode = tk.BooleanVar(value=False)
        self.create_pdf = tk.BooleanVar(value=False)
        self.progress_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(value="Ready")
        self.folder_summary_var = tk.StringVar(value="No folder selected")
        self.progress_text_var = tk.StringVar(value="0%")
        self.progress_detail_var = tk.StringVar(value="Waiting to start")

        self.cancel_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self.latest_dashboard_path = ""
        self.progress_canvas: tk.Canvas | None = None
        self.progress_fill_id: int | None = None
        self.progress_track_id: int | None = None
        self.progress_label_id: int | None = None
        self.threshold_dialog: ThresholdEditorDialog | None = None

        self._configure_styles()
        self._build_ui()
        self._refresh_test_values()

    def _open_dashboard(self, dashboard_path: str) -> None:
        """Open the generated dashboard in the default browser."""
        if not dashboard_path:
            return

        path = Path(dashboard_path)
        if not path.exists():
            self._append_log(f"Dashboard file not found: {dashboard_path}")
            return

        self.latest_dashboard_path = str(path.resolve())
        try:
            webbrowser.open(path.resolve().as_uri())
        except Exception as exc:
            self._append_log(f"Could not open dashboard automatically: {exc}")

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=10)

        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family="Segoe UI", size=10)

        heading_font = tkfont.nametofont("TkHeadingFont")
        heading_font.configure(family="Segoe UI Semibold", size=10)

        style.configure("App.TFrame", background="#e9eef5")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure(
            "Hero.TFrame",
            background="#133a5e",
            relief="flat",
        )
        style.configure(
            "HeroTitle.TLabel",
            background="#133a5e",
            foreground="#ffffff",
            font=("Segoe UI Semibold", 20),
        )
        style.configure(
            "HeroSub.TLabel",
            background="#133a5e",
            foreground="#d8e6f4",
            font=("Segoe UI", 10),
        )
        style.configure(
            "SectionTitle.TLabel",
            background="#ffffff",
            foreground="#17324d",
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "Muted.TLabel",
            background="#ffffff",
            foreground="#607285",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Status.TLabel",
            background="#ffffff",
            foreground="#17324d",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "InfoValue.TLabel",
            background="#ffffff",
            foreground="#17324d",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "ProgressValue.TLabel",
            background="#ffffff",
            foreground="#17324d",
            font=("Segoe UI Semibold", 18),
        )
        style.configure(
            "Primary.TButton",
            padding=(16, 10),
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Secondary.TButton",
            padding=(14, 10),
        )
        style.configure(
            "TLabelframe",
            background="#ffffff",
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "TLabelframe.Label",
            background="#ffffff",
            foreground="#17324d",
            font=("Segoe UI Semibold", 11),
        )
        style.configure(
            "TCheckbutton",
            background="#ffffff",
            foreground="#17324d",
        )
        style.map(
            "TCheckbutton",
            background=[("active", "#ffffff")],
        )
        style.configure(
            "TEntry",
            fieldbackground="#f8fafc",
            padding=8,
        )
        style.configure(
            "TCombobox",
            fieldbackground="#f8fafc",
            padding=6,
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#dbe4ee",
            background="#2f7ed8",
            bordercolor="#dbe4ee",
            lightcolor="#2f7ed8",
            darkcolor="#2f7ed8",
        )

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        root = ttk.Frame(self, style="App.TFrame", padding=18)
        root.grid(row=0, column=0, sticky="nsew")
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        hero = ttk.Frame(root, style="Hero.TFrame", padding=(24, 22))
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        hero.grid_columnconfigure(0, weight=1)

        ttk.Label(hero, text="Time Series Anomaly Detection", style="HeroTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            hero,
            text=(
                "Scalable desktop workflow for loading device data, running inference, "
                "and exporting anomaly reports."
            ),
            style="HeroSub.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            hero,
            textvariable=self.status_var,
            style="HeroSub.TLabel",
            anchor="e",
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        content = ttk.Frame(root, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=0, minsize=360)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        control_card = ttk.Frame(content, style="Card.TFrame", padding=18)
        control_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        control_card.grid_columnconfigure(0, weight=1)

        output_card = ttk.Frame(content, style="Card.TFrame", padding=18)
        output_card.grid(row=0, column=1, sticky="nsew")
        output_card.grid_columnconfigure(0, weight=1)
        output_card.grid_rowconfigure(2, weight=1)

        header_row = ttk.Frame(control_card, style="Card.TFrame")
        header_row.grid(row=0, column=0, sticky="ew")
        header_row.grid_columnconfigure(0, weight=1)

        ttk.Label(header_row, text="Configuration", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(
            header_row,
            text="Thresholds",
            style="Secondary.TButton",
            command=self.open_threshold_editor,
        ).grid(row=0, column=1, sticky="e")

        ttk.Label(
            control_card,
            text="Pick an input folder, select the target device, and decide which outputs to generate.",
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 14))

        form = ttk.LabelFrame(control_card, text="Run Setup", padding=14)
        form.grid(row=2, column=0, sticky="ew")
        form.grid_columnconfigure(1, weight=1)

        ttk.Label(form, text="Folder").grid(row=0, column=0, sticky="w", pady=(0, 10))
        folder_entry = ttk.Entry(form, textvariable=self.selected_folder)
        folder_entry.grid(row=0, column=1, sticky="ew", padx=(10, 10), pady=(0, 10))
        ttk.Button(form, text="Browse", style="Secondary.TButton", command=self.browse_folder).grid(
            row=0, column=2, sticky="e", pady=(0, 10)
        )

        ttk.Label(form, textvariable=self.folder_summary_var, style="Muted.TLabel", wraplength=300).grid(
            row=1, column=1, columnspan=2, sticky="w", pady=(0, 12)
        )

        ttk.Label(form, text="Device").grid(row=2, column=0, sticky="w", pady=(0, 10))
        self.device_combo = ttk.Combobox(
            form,
            textvariable=self.device_series,
            values=CFG.get_all_devices(),
            state="readonly",
        )
        self.device_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=(0, 10))
        self.device_combo.bind("<<ComboboxSelected>>", self.on_device_change)

        ttk.Label(form, text="Test").grid(row=3, column=0, sticky="w")
        self.test_label = ttk.Label(form, text="Test name")
        self.test_label.grid_remove()
        self.test_combo = ttk.Combobox(
            form,
            textvariable=self.test_name,
            values=[],
            state="readonly",
        )
        self.test_combo.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(10, 0))

        options = ttk.LabelFrame(control_card, text="Output Options", padding=14)
        options.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        options.grid_columnconfigure(0, weight=1)

        self.batch_check = ttk.Checkbutton(
            options,
            text="Run all tests for selected device",
            variable=self.batch_mode,
            command=self._toggle_batch_mode,
        )
        self.batch_check.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.plot_check = ttk.Checkbutton(
            options,
            text="Create plots for negative samples",
            variable=self.create_plot,
        )
        self.plot_check.grid(row=1, column=0, sticky="w", pady=4)

        self.pdf_check = ttk.Checkbutton(
            options,
            text="Create PDF reports",
            variable=self.create_pdf,
        )
        self.pdf_check.grid(row=2, column=0, sticky="w", pady=4)

        actions = ttk.Frame(control_card, style="Card.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(18, 0))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        actions.grid_columnconfigure(2, weight=1)

        self.exit_btn = ttk.Button(actions, text="Exit", style="Secondary.TButton", command=self.destroy)
        self.exit_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.cancel_btn = ttk.Button(
            actions,
            text="Cancel",
            style="Secondary.TButton",
            command=self.on_cancel,
            state="disabled",
        )
        self.cancel_btn.grid(row=0, column=1, sticky="ew", padx=4)

        self.start_btn = ttk.Button(actions, text="Start", style="Primary.TButton", command=self.on_start)
        self.start_btn.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        control_card.grid_rowconfigure(5, weight=1)
        self.open_report_btn = ttk.Button(
            control_card,
            text="Open Report",
            style="Secondary.TButton",
            command=lambda: self._open_dashboard(self.latest_dashboard_path),
        )
        self.open_report_btn.grid(row=6, column=0, sticky="w", pady=(16, 0))
        self.open_report_btn.grid_remove()

        ttk.Label(output_card, text="Run Monitor", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            output_card,
            text="Track progress, cancellation state, and runtime messages while the pipeline is active.",
            style="Muted.TLabel",
            wraplength=620,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 14))

        info_bar = ttk.Frame(output_card, style="Card.TFrame")
        info_bar.grid(row=2, column=0, sticky="ew")
        info_bar.grid_columnconfigure(1, weight=1)
        info_bar.grid_columnconfigure(2, weight=0)

        ttk.Label(info_bar, text="Status", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.status = ttk.Label(info_bar, textvariable=self.status_var, style="InfoValue.TLabel")
        self.status.grid(row=1, column=0, sticky="w", pady=(2, 0))

        progress_card = ttk.Frame(info_bar, style="Card.TFrame")
        progress_card.grid(row=0, column=1, rowspan=2, sticky="ew", padx=(24, 0))
        progress_card.grid_columnconfigure(0, weight=1)
        progress_card.grid_columnconfigure(1, weight=0)

        ttk.Label(progress_card, text="Progress", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(progress_card, textvariable=self.progress_text_var, style="ProgressValue.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        self.progress_detail_label = ttk.Label(
            progress_card,
            textvariable=self.progress_detail_var,
            style="Muted.TLabel",
            justify="left",
            anchor="w",
            wraplength=420,
        )
        self.progress_detail_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        self.progress_canvas = tk.Canvas(
            progress_card,
            height=22,
            bg="#ffffff",
            highlightthickness=0,
            bd=0,
        )
        self.progress_canvas.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.progress_canvas.bind("<Configure>", self._redraw_progress)
        progress_card.bind("<Configure>", self._on_progress_card_resize)

        log_frame = ttk.LabelFrame(output_card, text="Output Log", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        output_card.grid_rowconfigure(3, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            bg="#0f1720",
            fg="#d7e2ee",
            insertbackground="#d7e2ee",
            selectbackground="#27557f",
            font=("Consolas", 10),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Label(
            output_card,
            text="Tip: resize the window to expand the log area and keep long batch runs readable.",
            style="Muted.TLabel",
        )
        footer.grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.after(0, self._redraw_progress)

    def _set_status_text(self, text: str) -> None:
        self.after(0, lambda: self.status_var.set(text))

    def _redraw_progress(self, _event=None) -> None:
        if self.progress_canvas is None:
            return

        canvas = self.progress_canvas
        canvas.delete("all")

        width = max(40, canvas.winfo_width())
        height = max(18, canvas.winfo_height())
        pad = 2
        radius = 10
        progress = max(0.0, min(1.0, self.progress_var.get()))
        fill_width = max(radius * 2, int((width - pad * 2) * progress)) if progress > 0 else 0

        self._create_round_rect(canvas, pad, pad, width - pad, height - pad, radius, fill="#dbe5f0", outline="")
        if fill_width > 0:
            self._create_round_rect(
                canvas,
                pad,
                pad,
                min(width - pad, pad + fill_width),
                height - pad,
                radius,
                fill="#2f7ed8",
                outline="",
            )

    def _on_progress_card_resize(self, event) -> None:
        wraplength = max(180, event.width - 110)
        self.progress_detail_label.configure(wraplength=wraplength)
        self._redraw_progress()

    @staticmethod
    def _create_round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs):
        radius = min(radius, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2))
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _refresh_test_values(self) -> None:
        device = self.device_series.get().strip()
        enabled_tests = CFG.get_tests_for_device(device)

        self.test_combo["values"] = enabled_tests
        current_test = self.test_name.get().strip()

        if not enabled_tests:
            self.test_name.set("")
            self.test_combo.set("")
            self.test_combo.config(state="disabled")
            self.status_var.set(f"No tests mapped for {device}")
            return

        self.test_combo.config(state="readonly")

        if current_test in enabled_tests:
            self.test_combo.set(current_test)
        else:
            self.test_name.set(enabled_tests[0])
            self.test_combo.set(enabled_tests[0])

    def on_device_change(self, _event=None) -> None:
        self._refresh_test_values()

    def open_threshold_editor(self) -> None:
        if self.threshold_dialog is not None and self.threshold_dialog.winfo_exists():
            self.threshold_dialog.lift()
            self.threshold_dialog.focus_force()
            return
        self.threshold_dialog = ThresholdEditorDialog(self)
        self.threshold_dialog.protocol("WM_DELETE_WINDOW", self._close_threshold_editor)

    def _close_threshold_editor(self) -> None:
        if self.threshold_dialog is not None and self.threshold_dialog.winfo_exists():
            self.threshold_dialog.destroy()
        self.threshold_dialog = None

    def _toggle_batch_mode(self) -> None:
        if self.batch_mode.get():
            self.test_combo.config(state="disabled")
            self.test_combo.configure(foreground="#8a98a8")
        else:
            self.test_combo.config(state="readonly")
            self.test_combo.configure(foreground="#17324d")

    def browse_folder(self) -> None:
        config_file = Path.home() / ".ts_anomaly_config.json"

        try:
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    last_folder = config.get("last_folder", "")
                    initial_dir = last_folder if Path(last_folder).exists() else str(Path.home())
            else:
                initial_dir = str(Path.home())
        except (json.JSONDecodeError, IOError):
            initial_dir = str(Path.home())

        folder = filedialog.askdirectory(
            title="Select folder containing .dat files",
            initialdir=initial_dir,
        )
        if folder:
            self.selected_folder.set(folder)
            try:
                config = {}
                if config_file.exists():
                    with open(config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)
                config["last_folder"] = folder
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
            except IOError:
                pass

            dat_count = len(list(Path(folder).glob("*.dat")))
            if dat_count > 0:
                self.folder_summary_var.set(f"{dat_count} .dat file(s) found in {folder}")
                self.status_var.set(f"{dat_count} file(s) ready")
            else:
                self.folder_summary_var.set(f"No .dat files found in {folder}")
                self.status_var.set("Folder selected, but no .dat files found")

    def _append_log(self, message: str) -> None:
        clean_message = message.strip()
        if clean_message:
            lowered = clean_message.lower()
            if clean_message.startswith("Step "):
                self.after(0, lambda msg=clean_message: self.progress_detail_var.set(msg))
            elif lowered.startswith("running test "):
                self.after(0, lambda msg=clean_message: self.progress_detail_var.set(msg))
            elif "cancel" in lowered:
                self.after(0, lambda: self.progress_detail_var.set("Cancelling current work"))
            elif lowered.startswith("generating "):
                self.after(0, lambda msg=clean_message: self.progress_detail_var.set(msg))

        def _do():
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")

        self.after(0, _do)

    def _set_progress(self, value: float) -> None:
        def _do():
            clamped = max(0.0, min(1.0, value))
            self.progress_var.set(clamped)
            self.progress_text_var.set(f"{int(round(clamped * 100))}%")
            self._redraw_progress()

        self.after(0, _do)

    def _set_running_ui(self, running: bool) -> None:
        def _do():
            if running or not self.latest_dashboard_path:
                self.open_report_btn.grid_remove()
            else:
                self.open_report_btn.grid()
            self.start_btn.config(state=("disabled" if running else "normal"))
            self.exit_btn.config(state=("disabled" if running else "normal"))
            self.cancel_btn.config(state=("normal" if running else "disabled"))
            self.device_combo.config(state=("disabled" if running else "readonly"))
            if running or self.batch_mode.get():
                self.test_combo.config(state="disabled")
            else:
                self.test_combo.config(state="readonly")

        self.after(0, _do)

    def on_cancel(self) -> None:
        if self.cancel_event.is_set():
            return
        self.cancel_event.set()
        self._set_status_text("Cancelling...")
        self.after(0, lambda: self.cancel_btn.config(state="disabled"))
        self._append_log("Cancel requested...")

    def on_start(self) -> None:
        folder = self.selected_folder.get().strip()
        device_series = self.device_series.get().strip()
        test_name = self.test_name.get().strip()
        batch_mode = self.batch_mode.get()

        if not folder:
            messagebox.showwarning("Warning", "Please select a folder first.")
            self.status_var.set("No folder selected")
            return

        enabled_tests = set(CFG.get_tests_for_device(device_series))
        if not enabled_tests:
            messagebox.showwarning("Warning", f"No tests are enabled for {device_series}.")
            self.status_var.set("No enabled tests")
            return

        if not batch_mode and test_name not in enabled_tests:
            messagebox.showwarning("Warning", f"Selected test is not enabled for {device_series}.")
            self.status_var.set("Invalid test for device")
            return

        self.log_text.delete("1.0", "end")
        self.progress_var.set(0.0)
        self.progress_text_var.set("0%")
        self.progress_detail_var.set("Preparing run")
        self.status_var.set("Running...")
        self.open_report_btn.grid_remove()
        self.cancel_event.clear()
        self.after(0, self._redraw_progress)

        def worker():
            try:
                self._set_running_ui(True)
                dashboard_path = ""

                if batch_mode:
                    run_result = run_all_tests_for_device(
                        device_series=device_series,
                        input_folder=folder,
                        create_plot=self.create_plot.get(),
                        create_pdf=self.create_pdf.get(),
                        report=self._append_log,
                        set_progress=self._set_progress,
                        cancel_event=self.cancel_event,
                    )
                    if run_result:
                        dashboard_path = run_result.get("dashboard_index", "")
                else:
                    config = UserConfig(
                        folder=folder,
                        device_series=device_series,
                        test_name=test_name,
                        create_plot=self.create_plot.get(),
                        create_pdf=self.create_pdf.get(),
                    )
                    run_result = run_anomaly_detection(
                        config,
                        report=self._append_log,
                        set_progress=self._set_progress,
                        cancel_event=self.cancel_event,
                    )
                    if run_result:
                        dashboard_path = run_result.get("dashboard_index", "")

                if self.cancel_event.is_set():
                    self._set_status_text("Cancelled")
                else:
                    self._set_status_text("Finished")
                    if dashboard_path:
                        self._append_log(f"Opening dashboard: {dashboard_path}")
                        self.after(0, lambda path=dashboard_path: self._open_dashboard(path))

            except InterruptedError:
                self._append_log("Run cancelled.")
                self._set_status_text("Cancelled")
            except Exception as e:
                self._append_log(f"ERROR: {e}")
                self._set_status_text("Failed")
            finally:
                self._set_running_ui(False)
                self.after(0, self._refresh_test_values)

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()


if __name__ == "__main__":
    app = FolderPickerApp()
    app.mainloop()
