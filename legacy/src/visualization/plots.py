"""
Visualization module for anomaly detection results.

This module generates comparison plots between original and reconstructed time series,
highlighting anomalies with different colors (white, yellow, red) based on thresholds.

Functions:
    plot_anomaly: Generate plots with anomaly scores and save to output directory
"""

import os
import gc
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src.inference.model_inference import get_original_ts


def plot_anomaly(
    test_seq,
    test_pred,
    test_errors,
    ind: int,
    size_window: int,
    step_window: int,
    n_windows_per_ts: int,
    threshold1: float,
    threshold2: float,
    secdir: str,
    senu: str,
    testname: str,
    section: str,
    nb_ts_origine: int,
    nb_feature: int,
    cancel_fn: callable = None,
    create_plot: bool = True,
):
    """
    Plot original vs reconstructed time series with anomaly highlighting.
    Returns (errorlist, dclass) or (None, None) if cancelled.
    """
    if cancel_fn and cancel_fn():
        return None, None

    orig = get_original_ts(
        test_seq.data, size_window, step_window, nb_ts_origine, nb_feature
    )[ind]
    reco = get_original_ts(
        test_pred, size_window, step_window, nb_ts_origine, nb_feature
    )[ind]

    plt.figure(figsize=(12, 6), dpi=300)
    plt.plot(orig, label="Original", linewidth=1.2)
    plt.plot(reco, label="Reconstructed", linewidth=1.2)

    ax = plt.gca()
    n_points = orig.shape[0]

    start_win = ind * n_windows_per_ts
    end_win = (ind + 1) * n_windows_per_ts
    this_win_errors = test_errors[start_win:end_win]

    errorlist = []
    dclass = 0

    k = 0
    start = 0

    while start < n_points and k < len(this_win_errors):
        if cancel_fn and cancel_fn():
            plt.close()
            gc.collect()
            raise InterruptedError("Plotting cancelled")

        end = start + size_window
        error_val = this_win_errors[k]

        if error_val < threshold1:
            color = "white"
        elif threshold1 <= error_val <= threshold2:
            color = "yellow"
        else:
            color = "red"

        if this_win_errors[k] > threshold1:
            dclass = 1
            errorlist.append({
                "serial_number": str(senu),
                "test_name": str(testname),
                "section": str(section),
            })

        ax.axvline(start, linestyle="--", color="black", linewidth=0.8, alpha=0.3)
        ax.axvline(end, linestyle="--", color="black", linewidth=0.8, alpha=0.3)

        if k % 2 == 0:
            ax.axvspan(start, end, color=color, alpha=0.1, zorder=0)
            ax.text(
                (start + end) / 2,
                ax.get_ylim()[1],
                f"{this_win_errors[k]:.5f}",
                ha="center",
                va="top",
                fontsize=6,
                color="black",
                bbox=dict(
                    facecolor="white",
                    alpha=0.5,
                    edgecolor="none",
                    boxstyle="round,pad=0.2",
                ),
            )
        else:
            ax.axvspan(start, end, color=color, alpha=0.15, zorder=0)
            ax.text(
                (start + end) / 2,
                ax.get_ylim()[1],
                f"{this_win_errors[k]:.5f}",
                ha="center",
                va="bottom",
                fontsize=6,
                color="red",
                bbox=dict(
                    facecolor="white",
                    alpha=0.5,
                    edgecolor="none",
                    boxstyle="round,pad=0.2",
                ),
            )

        k += 1
        start += step_window

    plt.xlabel("Time Steps")
    plt.ylabel("Value")
    plt.title(
        f"Original vs Reconstructed Time Series with Anomaly Scores - {senu} - {testname}"
    )
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()

    # If create_plot is False and this is a negative sample (dclass=0), skip saving
    if not create_plot and dclass == 0:
        plt.close()
        gc.collect()
        return errorlist, dclass

    save_path = f"{str(secdir)}/{dclass}/{senu}.png"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches="tight")

    del orig, reco, this_win_errors
    gc.collect()
    plt.close()
    gc.collect()

    return errorlist, dclass
