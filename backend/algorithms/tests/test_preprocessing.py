from copy import deepcopy
from unittest import TestCase

from algorithms.preprocessing import iter_preprocessed_windows


class PreprocessingExecutionTests(TestCase):
    def window(self, **overrides):
        return {"type": "window", "size": 2, "tail": "drop", **overrides}

    def standardization(self, **overrides):
        return {"type": "normalize", "method": "standardize", "mean": [10], "scale": [2], **overrides}

    def profile(self, *steps):
        return {"schema_version": 1, "steps": list(steps)}

    def prepare(self, samples, *steps, **overrides):
        return iter_preprocessed_windows(samples, **{
            "preprocessing": self.profile(*steps), "input_spec": {"features": ["signal1"]},
            "stride": 1, **overrides,
        })

    def unused_samples(self):
        self.fail("An invalid execution plan must fail before consuming samples.")
        yield [1]

    def test_window_only_preserves_values_without_implicit_normalization(self):
        windows = list(self.prepare([[10], [20], [30], [40], [50]], self.window(), stride=2, offset=100))
        self.assertEqual([(window.start, window.end) for window in windows], [(100, 102), (102, 104)])
        self.assertEqual([window.values for window in windows], [((10,), (20,)), ((30,), (40,))])

    def test_normalization_before_and_after_windowing_preserves_feature_order(self):
        samples = [[8, 60], [10, 100], [14, 120]]
        normalize = self.standardization(mean=[10, 100], scale=[2, 20])
        for steps in ((normalize, self.window()), (self.window(), normalize)):
            with self.subTest(steps=steps):
                windows = list(self.prepare(samples, *steps, input_spec={"features": ["pressure", "temperature"]}))
                self.assertEqual([window.values for window in windows], [((-1, -2), (0, 0)), ((0, 0), (2, 1))])
                self.assertEqual([(window.start, window.end) for window in windows], [(0, 2), (1, 3)])

    def test_distinct_steps_retain_order_on_both_sides_of_windowing(self):
        first = self.standardization()
        second = {"type": "normalize", "method": "minmax", "scale": [0.5], "offset": [1], "range": [0, 10], "clip": False}
        third = self.standardization(mean=[1], scale=[2])
        for steps in (
            (first, second, third, self.window()),
            (self.window(), first, second, third),
            (first, self.window(), second, third),
        ):
            with self.subTest(steps=steps):
                windows = list(self.prepare([[10], [14], [18]], *steps))
                self.assertEqual([window.values for window in windows], [((0,), (0.5,)), ((0.5,), (1,))])

    def test_explicit_none_preserves_values(self):
        none = {"type": "normalize", "method": "none"}
        windows = list(self.prepare([[10], [14]], none, self.window(), none))
        self.assertEqual(windows[0].values, ((10,), (14,)))

    def test_empty_and_short_inputs_obey_declared_tail_policy(self):
        for tail in ("drop", "reject"):
            self.assertEqual(list(self.prepare([], self.window(tail=tail), self.standardization())), [])
        self.assertEqual(list(self.prepare([[10]], self.window())), [])
        with self.assertRaisesRegex(ValueError, "incomplete tail"):
            self.prepare([[10]], self.window(tail="reject"))

    def test_reject_tail_uses_runtime_stride_and_requires_exact_end(self):
        samples = [[value] for value in range(5)]
        with self.assertRaisesRegex(ValueError, "incomplete tail"):
            self.prepare(samples, self.window(tail="reject"), stride=2)
        windows = list(self.prepare(samples[:4], self.window(tail="reject"), stride=2))
        self.assertEqual([(window.start, window.end) for window in windows], [(0, 2), (2, 4)])

    def test_missing_window_is_rejected_before_consuming_input(self):
        with self.assertRaisesRegex(ValueError, "exactly one window"):
            self.prepare(self.unused_samples(), self.standardization())

    def test_resampling_reduces_values_and_maps_bounds_to_source_samples(self):
        expected = {"mean": (3, 12, 22), "min": (2, 10, 20), "max": (4, 14, 24)}
        for method in ("mean", "min", "max"):
            with self.subTest(method=method):
                windows = list(self.prepare(
                    [[value] for value in (2, 4, 10, 14, 20, 24)],
                    {"type": "resample", "method": method}, self.window(),
                    input_spec={"features": ["signal1"], "sample_rate_hz": 500},
                    source_sample_rate_hz=1000, offset=100,
                ))
                first, second, third = expected[method]
                self.assertEqual([window.values for window in windows], [((first,), (second,)), ((second,), (third,))])
                self.assertEqual([(window.start, window.end) for window in windows], [(100, 104), (102, 106)])
                self.assertEqual((windows[0].start / 1000, windows[0].end / 1000), (0.1, 0.104))

    def test_resampling_requires_explicit_supported_rates_before_consuming_input(self):
        for rate in (None, 0, True, float("nan"), float("inf"), 250):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                self.prepare(
                    self.unused_samples(), {"type": "resample", "method": "mean"}, self.window(),
                    input_spec={"features": ["signal1"], "sample_rate_hz": 500}, source_sample_rate_hz=rate,
                )

    def test_normalization_keeps_its_declared_order_relative_to_resampling(self):
        normalize = {"type": "normalize", "method": "minmax", "scale": [1], "offset": [0], "range": [0, 1], "clip": True}
        resample = {"type": "resample", "method": "mean"}
        options = {"input_spec": {"features": ["signal1"], "sample_rate_hz": 500}, "source_sample_rate_hz": 1000}
        before = list(self.prepare([[-2], [4], [6], [10]], normalize, resample, self.window(), **options))
        after = list(self.prepare([[-2], [4], [6], [10]], resample, self.window(), normalize, **options))
        self.assertEqual(before[0].values, ((0.5,), (1,)))
        self.assertEqual(after[0].values, ((1,), (1,)))
        self.assertEqual((before[0].start, before[0].end), (0, 4))
        self.assertEqual((after[0].start, after[0].end), (0, 4))

    def test_fractional_resampling_preserves_partial_final_extent(self):
        windows = list(self.prepare(
            [[value] for value in range(5)], {"type": "resample", "method": "mean"},
            self.window(size=3, tail="reject"), input_spec={"features": ["signal1"], "sample_rate_hz": 600},
            source_sample_rate_hz=1000, offset=7,
        ))
        self.assertEqual(windows[0].values, ((0.5,), (2.5,), (4,)))
        self.assertEqual((windows[0].start, windows[0].end), (7, 12))

    def test_resampling_and_window_tail_are_separate_policies(self):
        options = {"input_spec": {"features": ["signal1"], "sample_rate_hz": 500}, "source_sample_rate_hz": 1000, "stride": 2}
        samples = [[value] for value in range(5)]
        resample = {"type": "resample", "method": "mean"}
        dropped = list(self.prepare(samples, resample, self.window(), **options))
        self.assertEqual(dropped[0].values, ((0.5,), (2.5,)))
        self.assertEqual((dropped[0].start, dropped[0].end), (0, 4))
        with self.assertRaisesRegex(ValueError, "incomplete tail"):
            self.prepare(samples, resample, self.window(tail="reject"), **options)
        self.assertEqual(list(self.prepare([], resample, self.window(tail="reject"), **options)), [])

    def test_repeated_resampling_to_the_same_target_does_not_remap_twice(self):
        windows = list(self.prepare(
            [[value] for value in range(6)], {"type": "resample", "method": "mean"},
            {"type": "resample", "method": "max"}, self.window(),
            input_spec={"features": ["signal1"], "sample_rate_hz": 500}, source_sample_rate_hz=1000,
        ))
        self.assertEqual([window.values for window in windows], [((0.5,), (2.5,)), ((2.5,), (4.5,))])
        self.assertEqual([(window.start, window.end) for window in windows], [(0, 4), (2, 6)])

    def test_rate_mismatch_without_declared_resampling_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "declare a resample"):
            self.prepare(
                self.unused_samples(), self.window(), source_sample_rate_hz=1000,
                input_spec={"features": ["signal1"], "sample_rate_hz": 500},
            )
        windows = list(self.prepare(
            [[1], [2]], self.window(), source_sample_rate_hz=500,
            input_spec={"features": ["signal1"], "sample_rate_hz": 500},
        ))
        self.assertEqual(windows[0].values, ((1,), (2,)))

    def test_unconfigured_and_invalid_declarations_fail_before_consuming_input(self):
        for profile in (
            None, {}, [], False, {"schema_version": 2, "steps": [self.window()]},
            {"schema_version": True, "steps": [self.window()]}, self.profile(),
            self.profile(self.window(), self.window()), self.profile({"type": "unknown"}),
            self.profile(self.window(tail="pad")), self.profile(self.window(size=0)),
            self.profile(self.standardization(scale=[0]), self.window()),
            self.profile(self.window(), self.standardization(extra=1)),
            self.profile(self.window(), {"type": "resample", "method": "mean"}),
        ):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                self.prepare(self.unused_samples(), preprocessing=profile)

    def test_input_spec_is_validated_before_consuming_input(self):
        for spec in (
            None, {}, {"features": []}, {"features": ["x", "x"]},
            {"features": [" x"]}, {"features": [1]}, {"features": ["x"], "unknown": 1},
            {"features": ["x"], "sample_rate_hz": 0}, {"features": ["x"], "sample_rate_hz": True},
            {"features": ["x"], "sample_rate_hz": float("nan")},
        ):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                self.prepare(self.unused_samples(), self.window(), input_spec=spec)

    def test_fitted_vectors_must_match_declared_features_even_without_windows(self):
        for samples in ([], [[10]]):
            with self.subTest(samples=samples), self.assertRaisesRegex(ValueError, "per input feature"):
                self.prepare(samples, self.window(), self.standardization(mean=[0, 0], scale=[1, 1]))

    def test_actual_feature_count_must_match_input_spec_without_normalization(self):
        with self.assertRaisesRegex(ValueError, "feature count"):
            self.prepare([[1, 2], [3, 4]], self.window())

    def test_invalid_runtime_options_fail_before_consuming_input(self):
        for stride in (0, -1, True, 1.5, "1", None):
            with self.subTest(stride=stride), self.assertRaisesRegex(ValueError, "stride"):
                self.prepare(self.unused_samples(), self.window(), stride=stride)
        for offset in (-1, True, 1.5, "0", None):
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "offset"):
                self.prepare(self.unused_samples(), self.window(), offset=offset)

    def test_invalid_samples_are_rejected_even_in_a_dropped_tail(self):
        for samples in (None, "12", [[1], [2, 3]], [[True]], [[1], [2], [float("nan")]]):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                self.prepare(samples, self.window())

    def test_snapshots_protect_lazy_execution_without_modifying_caller_data(self):
        samples = [[10], [14], [18]]
        profile = self.profile(self.window(), self.standardization())
        original_samples, original_profile = deepcopy(samples), deepcopy(profile)
        windows = self.prepare(samples, preprocessing=profile)
        self.assertEqual(samples, original_samples)
        self.assertEqual(profile, original_profile)
        samples[1][0] = 999
        profile["steps"][1]["mean"][0] = 999
        profile["steps"][1]["scale"][0] = 99
        profile["steps"].append({"type": "normalize", "method": "unknown"})
        self.assertEqual([window.values for window in windows], [((0,), (2,)), ((2,), (4,))])

    def test_sample_generators_are_supported(self):
        windows = list(self.prepare(([value] for value in (10, 14, 18)), self.standardization(), self.window()))
        self.assertEqual([window.values for window in windows], [((0,), (2,)), ((2,), (4,))])

    def test_pre_window_arithmetic_errors_are_eager(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            self.prepare([[1e308], [1e308]], self.standardization(mean=[0], scale=[1e-308]), self.window())

    def test_post_window_arithmetic_errors_are_lazy_and_include_window_bounds(self):
        normalize = {"type": "normalize", "method": "minmax", "scale": [2], "offset": [0], "range": [0, 1], "clip": False}
        windows = self.prepare([[1], [2], [1e308]], self.window(), normalize, offset=100)
        self.assertEqual(next(windows).values, ((2,), (4,)))
        with self.assertRaisesRegex(ValueError, r"window \[101, 103\).*non-finite"):
            next(windows)
