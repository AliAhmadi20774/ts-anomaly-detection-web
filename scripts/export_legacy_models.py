"""Export the audited legacy LSTM inference configuration as a portable bundle.

This migration tool reads the CONFIG literal without importing legacy modules.
The 1 kHz source rate, signal aliases and lack of normalization come from the
legacy loader and preprocessing implementation, not from training metadata.
"""

import argparse
import ast
from fractions import Fraction
import json
from pathlib import Path
import shutil


def export_bundle(legacy_root: Path, destination: Path) -> dict:
    """Copy each distinct configured model once and retain the full source config."""
    legacy_root = legacy_root.resolve()
    tree = ast.parse((legacy_root / "src/config/global_config.py").read_text(encoding="utf-8-sig"))
    declarations = [
        node.value for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        and node.target.id == "CONFIG"
    ]
    if len(declarations) != 1:
        raise ValueError("Expected exactly one literal CONFIG declaration.")
    config = ast.literal_eval(declarations[0])
    models = []
    bindings = []
    sources = []
    for device, tests in config.items():
        if not 1 <= len(device) <= 64 or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in device):
            raise ValueError("Device names must be safe storage folder names.")
        for test_name, test in tests.items():
            sections = test["sections"]
            order = test["sections_order"]
            if len(order) != len(set(order)) or set(order) != set(sections):
                raise ValueError("Section order must include every section exactly once.")
            for section_name in order:
                section = sections[section_name]
                if section["transfo"] != ["mean"]:
                    raise ValueError("This adapter supports only the audited single mean feature.")
                period_ms = Fraction(section["resample_freq"])
                if period_ms < 1:
                    raise ValueError("Upsampling is not supported by the new preprocessing pipeline.")
                source = (legacy_root / section["model_path"]).resolve()
                if not source.is_relative_to(legacy_root) or not source.is_file():
                    raise ValueError("Checkpoint must be an existing file inside the legacy root.")
                metadata = {
                    "device_folder": device,
                    "architecture_params": {key: section[key] for key in ("hidden_size", "num_layers", "dropout")},
                    "input_spec": {"features": ["signal1"], "sample_rate_hz": float(1000 / period_ms)},
                    "preprocessing": {"schema_version": 1, "steps": [
                        {"type": "resample", "method": "mean"},
                        {"type": "normalize", "method": "none"},
                        {"type": "window", "size": section["size_window"], "tail": "drop"},
                    ]},
                }
                # Reused checkpoints share a version only when their input recipe
                # also agrees. Section ranges and stride belong to execution.
                identity = (source, json.dumps(metadata, sort_keys=True))
                if identity not in sources:
                    sources.append(identity)
                    version = len(models) + 1
                    models.append({
                        "algorithm": "lstm_ae", "version": version, **metadata,
                        "weights": f"{device}/lstm_ae/v{version}/weights.bin",
                    })
                model = models[sources.index(identity)]
                bindings.append({
                    "device": device, "test": test_name, "section": section_name,
                    "algorithm": model["algorithm"], "version": model["version"],
                })
    if not models:
        raise ValueError("No configured models were found.")
    manifest = {
        "schema_version": 1,
        "models": models,
        "legacy": {
            "config": config,
            "bindings": bindings,
            "inference_contract": {
                "source_sample_rate_hz": 1000,
                "signal_aliases": ["signal1", "Signal1"],
                "reconstruction_repeats": 10,
                "short_nonempty_signal": "zero_pad_to_expected_len",
                "empty_signal": "do_not_score",
                "long_signal": "preserve_then_slice_sections",
            },
            "note": "Migrated inference settings; training preprocessing is not independently verified. "
                    "Bindings, section ranges, stride, batch sizes, thresholds and length policies "
                    "are preserved here only; importing does not activate or persist an analysis policy.",
        },
    }
    payload = json.dumps(manifest, indent=2, allow_nan=False) + "\n"
    # Never mix an export with an old bundle. Validate the complete plan first.
    destination.mkdir(parents=True, exist_ok=False)
    for model, (source, _) in zip(models, sources, strict=True):
        target = destination / model["weights"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (destination / "manifest.json").write_text(payload, encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy_root", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    result = export_bundle(arguments.legacy_root, arguments.destination)
    print(f"Exported {len(result['models'])} model(s) and {len(result['legacy']['bindings'])} section bindings.")
