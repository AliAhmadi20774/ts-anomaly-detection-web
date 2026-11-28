from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.export_legacy_models import export_bundle


class LegacyExportTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.legacy = self.root / "legacy"
        (self.legacy / "src/config").mkdir(parents=True)
        checkpoint = self.legacy / "checkpoints/device1/weights"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(b"checkpoint copied without deserialization")
        self.section = {
            "start": 0, "end": 1000, "batch_size": 100, "step_window": 25,
            "size_window": 50, "resample_freq": "1", "transfo": ["mean"],
            "hidden_size": 300, "num_layers": 1, "dropout": 0.2,
            "model_path": "checkpoints/device1/weights", "threshold1": 0.35, "threshold2": 0.36,
        }
        test = {"expected_len": 22528, "sections_order": ["first", "second"], "sections": {
            "first": self.section, "second": {**self.section, "start": 1000, "end": 2000},
        }}
        self.config = {"device1": {"test1": test, "test2": deepcopy(test)}}
        self.destination = self.root / "bundle"

    def export(self, extra_code=""):
        (self.legacy / "src/config/global_config.py").write_text(
            f"CONFIG: dict = {self.config!r}\n{extra_code}", encoding="utf-8",
        )
        return export_bundle(self.legacy, self.destination)

    def test_shared_weights_export_once_and_all_original_settings_are_preserved(self):
        result = self.export()
        self.assertEqual(len(result["models"]), 1)
        self.assertEqual(len(result["legacy"]["bindings"]), 4)
        self.assertEqual(result["legacy"]["config"], self.config)
        self.assertEqual(result["models"][0]["input_spec"], {"features": ["signal1"], "sample_rate_hz": 1000})
        self.assertEqual(result["models"][0]["preprocessing"]["steps"], [
            {"type": "resample", "method": "mean"}, {"type": "normalize", "method": "none"},
            {"type": "window", "size": 50, "tail": "drop"},
        ])
        self.assertEqual(json.loads((self.destination / "manifest.json").read_text()), result)
        self.assertEqual((self.destination / result["models"][0]["weights"]).read_bytes(), b"checkpoint copied without deserialization")

    def test_config_is_parsed_without_executing_python(self):
        self.export("raise RuntimeError('must not execute')")
        self.assertTrue((self.destination / "manifest.json").exists())

    def test_changed_input_recipe_gets_a_separate_version_and_correct_bindings(self):
        self.config["device1"]["test2"]["sections"]["first"]["size_window"] = 75
        result = self.export()
        self.assertEqual([model["version"] for model in result["models"]], [1, 2])
        self.assertEqual([binding["version"] for binding in result["legacy"]["bindings"]], [1, 1, 2, 1])

    def test_fractional_resampling_period_is_translated_to_hz(self):
        for test in self.config["device1"].values():
            for section in test["sections"].values():
                section["resample_freq"] = "2.5"
        result = self.export()
        self.assertEqual(result["models"][0]["input_spec"]["sample_rate_hz"], 400)

    def test_unsupported_transformation_missing_weights_and_path_escape_fail_before_export(self):
        original = deepcopy(self.section)
        for changes in [
            {"transfo": ["mean", "max"]}, {"resample_freq": "0.5"},
            {"model_path": "missing"}, {"model_path": "../outside"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.section.update(changes)
                self.export()
            self.section.clear()
            self.section.update(original)
            self.assertFalse(self.destination.exists())

    def test_existing_bundle_is_never_overwritten(self):
        self.export()
        with self.assertRaises(FileExistsError):
            self.export()
