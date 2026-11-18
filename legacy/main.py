"""
Main entry point for Time Series Anomaly Detection application.
"""

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()

    from src.gui.app import FolderPickerApp

    app = FolderPickerApp()
    app.mainloop()
