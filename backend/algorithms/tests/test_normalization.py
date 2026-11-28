from copy import deepcopy
from unittest import TestCase

from algorithms.normalization import normalize_samples
from algorithms.windowing import iter_windows


class NormalizationTests(TestCase):
    def standardization(self, **overrides):
        return {
            "type": "normalize", "method": "standardize",
            "mean": [10, 100], "scale": [2, 20], **overrides,
        }

    def minmax(self, **overrides):
        return {
            "type": "normalize", "method": "minmax", "scale": [0.1, 0.01],
            "offset": [-1, -1], "range": [0, 1], "clip": False, **overrides,
        }

    def test_none_preserves_order_and_returns_immutable_float_rows(self):
        result = normalize_samples([[3, 20], [1, 10]], step={"type": "normalize", "method": "none"})
        self.assertEqual(result, ((3.0, 20.0), (1.0, 10.0)))
        self.assertIs(type(result[0][0]), float)
        with self.assertRaises(TypeError):
            result[0][0] = 99

    def test_standardization_uses_fitted_parameters_in_feature_order(self):
        result = normalize_samples([[8, 60], [10, 100], [14, 120]], step=self.standardization())
        self.assertEqual(result, ((-1, -2), (0, 0), (2, 1)))

    def test_parameters_are_not_refitted_for_a_new_batch(self):
        # A high-valued batch must retain large scores rather than being centered.
        step = self.standardization(mean=[10], scale=[2])
        alone = normalize_samples([[100]], step=step)
        batch = normalize_samples([[100], [1000]], step=step)
        self.assertEqual(alone, ((45,),))
        self.assertEqual(batch, ((45,), (495,)))

    def test_minmax_can_extrapolate_beyond_training_range(self):
        result = normalize_samples([[0, 50], [15, 150], [30, 250]], step=self.minmax())
        self.assertEqual(result, ((-1, -0.5), (0.5, 0.5), (2, 1.5)))

    def test_minmax_clips_each_feature_to_a_non_default_range(self):
        step = self.minmax(scale=[0.2, 0.02], offset=[-3, -3], range=[-1, 1], clip=True)
        result = normalize_samples([[0, 50], [15, 150], [30, 250]], step=step)
        self.assertEqual(result, ((-1, -1), (0, 0), (1, 1)))

    def test_constant_feature_uses_explicit_training_coefficients(self):
        standardized = normalize_samples([[5], [7]], step=self.standardization(mean=[5], scale=[1]))
        scaled = normalize_samples([[5], [7]], step=self.minmax(scale=[0], offset=[0.25]))
        self.assertEqual(standardized, ((0,), (2,)))
        self.assertEqual(scaled, ((0.25,), (0.25,)))

    def test_empty_input_still_validates_the_step(self):
        for step in ({"type": "normalize", "method": "none"}, self.standardization(), self.minmax()):
            with self.subTest(step=step):
                self.assertEqual(normalize_samples([], step=step), ())
        with self.assertRaises(ValueError):
            normalize_samples([], step=self.standardization(scale=[0, 1]))

    def test_generators_are_supported_without_changing_source_or_parameters(self):
        source = [[8, 60], [14, 120]]
        step = self.standardization()
        original_source, original_step = deepcopy(source), deepcopy(step)
        result = normalize_samples((iter(row) for row in source), step=step)
        self.assertEqual(result, ((-1, -2), (2, 1)))
        self.assertEqual(source, original_source)
        self.assertEqual(step, original_step)
        source[0][0] = 99
        self.assertEqual(result[0], (-1, -2))

    def test_parameter_count_must_match_actual_features(self):
        for step in (self.standardization(), self.minmax()):
            for samples in ([[1]], [[1, 2, 3]]):
                with self.subTest(step=step, samples=samples), self.assertRaisesRegex(ValueError, "per input feature"):
                    normalize_samples(samples, step=step)

    def test_invalid_step_types_methods_and_extra_fields_are_rejected(self):
        for step in (
            None, [], {}, {"type": "window", "size": 2, "tail": "drop"},
            {"type": "normalize", "method": "unknown"},
            {"type": "normalize", "method": "none", "mean": [0]},
            {"method": "none"}, self.standardization(extra=1),
        ):
            with self.subTest(step=step), self.assertRaises(ValueError):
                normalize_samples([[1, 2]], step=step)

    def test_standardization_requires_valid_fitted_vectors(self):
        for changes in (
            {"mean": []}, {"mean": [0]}, {"mean": [True, 0]}, {"mean": ["0", 0]},
            {"mean": [float("nan"), 0]}, {"mean": [10 ** 1000, 0]},
            {"scale": [0, 1]}, {"scale": [-1, 1]}, {"scale": [float("inf"), 1]},
            {"scale": [1]}, {"scale": None},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize_samples([[1, 2]], step=self.standardization(**changes))
        step = self.standardization()
        del step["mean"]
        with self.assertRaises(ValueError):
            normalize_samples([[1, 2]], step=step)

    def test_minmax_requires_valid_fitted_state_and_explicit_clip(self):
        for changes in (
            {"scale": [-1, 1]}, {"scale": [1]}, {"offset": [0]},
            {"offset": [float("inf"), 0]}, {"range": [0, 0]}, {"range": [1, 0]},
            {"range": [-1e308, 1e308]}, {"range": [0, 1, 2]},
            {"clip": "false"}, {"clip": 0},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize_samples([[1, 2]], step=self.minmax(**changes))
        step = self.minmax()
        del step["clip"]
        with self.assertRaises(ValueError):
            normalize_samples([[1, 2]], step=step)

    def test_invalid_measurements_are_rejected_even_without_normalization(self):
        for samples in (
            None, "12", [1, 2], [[1], [2, 3]], [[]], [[True]], [["1"]],
            {0: [1]}, [{1, 2}], [[float("nan")]], [[float("inf")]], [[10 ** 1000]],
        ):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                normalize_samples(samples, step={"type": "normalize", "method": "none"})

    def test_arithmetic_overflow_is_rejected_before_clipping(self):
        for step in (
            self.standardization(mean=[-1e308], scale=[1]),
            self.standardization(mean=[0], scale=[1e-308]),
            self.minmax(scale=[2], offset=[0], clip=False),
            self.minmax(scale=[2], offset=[0], clip=True),
        ):
            with self.subTest(step=step), self.assertRaisesRegex(ValueError, "non-finite.*sample 0, feature 0"):
                normalize_samples([[1e308]], step=step)

    def test_normalization_composes_with_windowing_without_changing_bounds(self):
        samples = [[8, 60], [10, 100], [14, 120]]
        step = self.standardization()
        before = list(iter_windows(
            normalize_samples(samples, step=step), window_size=2, stride=1, tail="reject", offset=100,
        ))
        original = list(iter_windows(samples, window_size=2, stride=1, tail="reject", offset=100))
        after = [normalize_samples(window.values, step=step) for window in original]
        self.assertEqual([(window.start, window.end) for window in before], [(100, 102), (101, 103)])
        self.assertEqual([window.values for window in before], after)
        self.assertEqual(before[0].values, ((-1, -2), (0, 0)))
