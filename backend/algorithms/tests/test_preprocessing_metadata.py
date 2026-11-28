from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from algorithms.models import Algorithm, ModelVersion
from algorithms.normalization import normalize_samples


class PreprocessingTests(TestCase):
    def model(self, preprocessing=None, **overrides):
        return ModelVersion(
            **{
                "algorithm": Algorithm.objects.get(key="lstm_ae"), "version": 1,
                "input_spec": {"features": ["pressure", "temperature"], "sample_rate_hz": 1000},
                "preprocessing": preprocessing, **overrides,
            }
        )

    def profile(self, *steps):
        return {"schema_version": 1, "steps": list(steps)}

    def assert_invalid(self, value, **overrides):
        with self.assertRaises(ValidationError) as result:
            self.model(value, **overrides).full_clean()
        self.assertIn("preprocessing", result.exception.message_dict)

    def test_unconfigured_is_distinct_from_explicit_no_normalization(self):
        unconfigured = self.model()
        unconfigured.full_clean()
        unconfigured.save()
        explicit = self.model(self.profile({"type": "normalize", "method": "none"}), version=2)
        explicit.full_clean()
        explicit.save()
        unconfigured.refresh_from_db()
        explicit.refresh_from_db()
        self.assertIsNone(unconfigured.preprocessing)
        self.assertEqual(explicit.preprocessing, self.profile({"type": "normalize", "method": "none"}))

    def test_ordered_steps_and_fitted_standardization_round_trip(self):
        profile = self.profile(
            {"type": "resample", "method": "mean"},
            {"type": "window", "size": 50, "tail": "drop"},
            {"type": "normalize", "method": "standardize", "mean": [1, -2], "scale": [2, 1]},
        )
        model = self.model(profile)
        model.full_clean()
        model.save()
        model.refresh_from_db()
        self.assertEqual(model.preprocessing, profile)

    def test_minmax_preserves_fitted_affine_parameters_and_clipping_policy(self):
        profile = self.profile({
            "type": "normalize", "method": "minmax", "scale": [0.1, 0],
            "offset": [-1, 0], "range": [0, 1], "clip": False,
        })
        model = self.model(profile)
        model.full_clean()
        model.save()
        model.refresh_from_db()
        self.assertEqual(model.preprocessing, profile)

    def test_saved_normalization_step_can_be_executed_in_input_feature_order(self):
        model = self.model(self.profile({
            "type": "normalize", "method": "standardize", "mean": [10, 100], "scale": [2, 20],
        }))
        model.full_clean()
        model.save()
        model.refresh_from_db()
        # Columns are pressure, temperature, as declared in input_spec.features.
        result = normalize_samples([[8, 60], [14, 120]], step=model.preprocessing["steps"][0])
        self.assertEqual(result, ((-1, -2), (2, 1)))

    def test_unknown_schemas_empty_values_and_unknown_steps_are_rejected(self):
        for value in [
            {}, [], "", 0, False, {"schema_version": 1, "steps": []},
            {"schema_version": True, "steps": [{"type": "normalize", "method": "none"}]},
            {"schema_version": 1.0, "steps": [{"type": "normalize", "method": "none"}]},
            {"schema_version": 2, "steps": [{"type": "normalize", "method": "none"}]},
            {"schema_version": 1, "steps": [], "extra": 1},
            self.profile("window"), self.profile({"type": "custom_python"}),
            self.profile({"type": "normalize", "method": "unknown"}),
            self.profile({"type": "normalize", "method": "none", "mean": [0]}),
        ]:
            with self.subTest(value=value):
                self.assert_invalid(value)

    def test_window_size_tail_and_resampling_order_are_explicit(self):
        window = {"type": "window", "size": 50, "tail": "drop"}
        for size in [0, -1, True, 1.5, "50"]:
            self.assert_invalid(self.profile({**window, "size": size}))
        for steps in [
            [{"type": "window", "size": 50}], [{**window, "stride": 25}],
            [{**window, "tail": "pad"}], [window, window],
            [window, {"type": "resample", "method": "mean"}],
            [{"type": "resample", "method": "interpolate"}],
        ]:
            with self.subTest(steps=steps):
                self.assert_invalid(self.profile(*steps))
        self.model(self.profile({**window, "tail": "reject"})).full_clean()

    def test_standardization_state_must_be_finite_positive_and_match_features(self):
        step = {"type": "normalize", "method": "standardize", "mean": [1, 2], "scale": [1, 2]}
        for changes in [
            {"mean": []}, {"mean": [0]}, {"mean": [True, 2]}, {"scale": [0, 1]},
            {"scale": [-1, 1]}, {"scale": [1]}, {"scale": [float("inf"), 1]},
            {"mean": [float("nan"), 1]}, {"mean": [10 ** 1000, 1]},
            {"mean": [1, 2, 3], "scale": [1, 2, 3]},
        ]:
            with self.subTest(changes=changes):
                self.assert_invalid(self.profile({**step, **changes}))

    def test_minmax_requires_valid_fitted_state_range_and_boolean_clip(self):
        step = {
            "type": "normalize", "method": "minmax", "scale": [1, 2],
            "offset": [0, 0], "range": [0, 1], "clip": False,
        }
        for changes in [
            {"scale": [-1, 1]}, {"offset": [0]}, {"offset": [float("inf"), 0]},
            {"range": [1, 0]}, {"range": [1, 1]}, {"range": [0, 1, 2]},
            {"range": [-1e308, 1e308]}, {"clip": "false"},
            {"scale": [1], "offset": [0]},
        ]:
            with self.subTest(changes=changes):
                self.assert_invalid(self.profile({**step, **changes}))
        missing = deepcopy(step)
        missing.pop("clip")
        self.assert_invalid(self.profile(missing))

    def test_resampling_uses_sample_rate_from_input_spec(self):
        profile = self.profile({"type": "resample", "method": "mean"})
        self.assert_invalid(profile, input_spec={"features": ["pressure"]})
        self.assert_invalid(self.profile({"type": "resample", "method": "mean", "sample_rate_hz": 1000}))

    def test_database_accepts_null_or_object_and_rejects_other_json_types(self):
        for value in [[], "text", 7, False]:
            with self.subTest(value=value), self.assertRaises(IntegrityError), transaction.atomic():
                self.model(value).save()
