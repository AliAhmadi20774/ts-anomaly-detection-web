from dataclasses import FrozenInstanceError
from sys import float_info
from unittest import TestCase

from algorithms.resampling import resample_samples


class ResamplingTests(TestCase):
    def resample(self, samples, **overrides):
        return resample_samples(samples, **{
            "source_sample_rate_hz": 1000, "target_sample_rate_hz": 500,
            "method": "mean", **overrides,
        })

    def test_mean_reduces_each_feature_in_input_order(self):
        result = self.resample([[2, 30], [4, 10], [10, 80], [14, 40]])
        self.assertEqual(result.values, ((3, 20), (12, 60)))
        self.assertEqual(result.source_bounds, ((0, 2), (2, 4)))
        self.assertEqual((result.source_sample_rate_hz, result.sample_rate_hz), (1000, 500))

    def test_min_and_max_reduce_each_feature_independently(self):
        samples = [[2, 30], [4, 10], [10, 80], [14, 40]]
        self.assertEqual(self.resample(samples, method="min").values, ((2, 10), (10, 40)))
        self.assertEqual(self.resample(samples, method="max").values, ((4, 30), (14, 80)))

    def test_partial_last_bin_includes_available_samples_without_padding(self):
        result = self.resample([[2], [4], [10], [14], [20]])
        self.assertEqual(result.values, ((3,), (12,), (20,)))
        self.assertEqual(result.source_bounds, ((0, 2), (2, 4), (4, 5)))
        start, end = result.source_bounds[-1]
        self.assertEqual((start / result.source_sample_rate_hz, end / result.source_sample_rate_hz), (0.004, 0.005))

    def test_fractional_ratio_uses_left_closed_time_bins(self):
        result = self.resample([[value] for value in range(10)], target_sample_rate_hz=600)
        self.assertEqual(result.source_bounds, ((0, 2), (2, 4), (4, 5), (5, 7), (7, 9), (9, 10)))
        self.assertEqual(result.values, ((0.5,), (2.5,), (4,), (5.5,), (7.5,), (9,)))

    def test_decimal_rates_do_not_accumulate_boundary_drift(self):
        result = self.resample([[value] for value in range(12)], source_sample_rate_hz=0.3, target_sample_rate_hz=0.1)
        self.assertEqual(result.source_bounds, ((0, 3), (3, 6), (6, 9), (9, 12)))
        self.assertEqual(result.values, ((1,), (4,), (7,), (10,)))

    def test_no_empty_trailing_bin_is_created_after_the_last_sample_time(self):
        for method, expected in (("mean", 3), ("min", 2), ("max", 4)):
            with self.subTest(method=method):
                result = self.resample([[2], [4]], target_sample_rate_hz=600, method=method)
                self.assertEqual(result.values, ((expected,),))
                self.assertEqual(result.source_bounds, ((0, 2),))

    def test_equal_rates_preserve_values_for_every_method(self):
        for method in ("mean", "min", "max"):
            with self.subTest(method=method):
                result = self.resample([[2, 20], [4, 10]], target_sample_rate_hz=1000, method=method)
                self.assertEqual(result.values, ((2, 20), (4, 10)))
                self.assertEqual(result.source_bounds, ((0, 1), (1, 2)))

    def test_empty_and_single_sample_inputs(self):
        empty = self.resample([])
        self.assertEqual(empty.values, ())
        self.assertEqual(empty.source_bounds, ())
        single = self.resample([[7]])
        self.assertEqual(single.values, ((7,),))
        self.assertEqual(single.source_bounds, ((0, 1),))

    def test_mean_handles_extreme_finite_and_subnormal_values(self):
        for values, expected in (
            ([float_info.max, float_info.max], float_info.max),
            ([1e308, -1e308], 0), ([5e-324, 5e-324], 5e-324),
        ):
            with self.subTest(values=values):
                self.assertEqual(self.resample([[value] for value in values]).values, ((expected,),))

    def test_generator_input_is_copied_and_outputs_are_immutable(self):
        samples = [[2], [4]]
        result = self.resample((iter(row) for row in samples))
        self.assertEqual(samples, [[2], [4]])
        samples[0][0] = 999
        self.assertEqual(result.values, ((3,),))
        with self.assertRaises(TypeError):
            result.values[0][0] = 0
        with self.assertRaises(FrozenInstanceError):
            result.sample_rate_hz = 0

    def test_invalid_rates_and_upsampling_are_rejected_even_for_empty_input(self):
        for name in ("source_sample_rate_hz", "target_sample_rate_hz"):
            for value in (None, 0, -1, True, "1000", float("nan"), float("inf"), 10 ** 1000):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    self.resample([], **{name: value})
        with self.assertRaisesRegex(ValueError, "cannot upsample"):
            self.resample([], target_sample_rate_hz=2000)

    def test_invalid_methods_and_measurements_are_rejected(self):
        for method in (None, "median", "raw", True):
            with self.subTest(method=method), self.assertRaises(ValueError):
                self.resample([], method=method)
        for samples in (None, "12", [[1], [2, 3]], [[]], [[True]], [[float("nan")]], [[1], [float("inf")]]):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                self.resample(samples)

    def test_bounds_partition_all_source_samples_for_various_rate_ratios(self):
        # Every input sample must belong to exactly one bin containing its time.
        for length in (0, 1, 2, 7, 31):
            for target in (1000, 600, 333.3, 1):
                with self.subTest(length=length, target=target):
                    result = self.resample([[value] for value in range(length)], target_sample_rate_hz=target)
                    indices = [index for start, end in result.source_bounds for index in range(start, end)]
                    self.assertEqual(indices, list(range(length)))
                    for bin_index, (start, end) in enumerate(result.source_bounds):
                        self.assertLess(start, end)
                        self.assertGreaterEqual(start / 1000 + 1e-12, bin_index / target)
                        self.assertLess((end - 1) / 1000, (bin_index + 1) / target)
