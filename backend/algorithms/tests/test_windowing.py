from dataclasses import FrozenInstanceError
from unittest import TestCase

from algorithms.windowing import iter_windows


class WindowingTests(TestCase):
    def windows(self, values, **overrides):
        return list(iter_windows(
            [[value] for value in values],
            **{"window_size": 3, "stride": 1, "tail": "drop", **overrides},
        ))

    def test_overlapping_values_and_exclusive_bounds(self):
        windows = self.windows([1, 2, 3, 4, 5, 6])
        self.assertEqual([(w.start, w.end) for w in windows], [(0, 3), (1, 4), (2, 5), (3, 6)])
        self.assertEqual(windows[0].values, ((1.0,), (2.0,), (3.0,)))
        self.assertEqual(windows[-1].values, ((4.0,), (5.0,), (6.0,)))

    def test_thousand_samples_produce_thirty_nine_complete_windows(self):
        windows = self.windows(range(1000), window_size=50, stride=25)
        self.assertEqual(len(windows), 39)
        self.assertEqual((windows[0].start, windows[0].end), (0, 50))
        self.assertEqual((windows[-1].start, windows[-1].end), (950, 1000))
        self.assertEqual(windows[-1].values, tuple((float(value),) for value in range(950, 1000)))

    def test_features_remain_in_input_order(self):
        windows = list(iter_windows(
            [[20, 1], [21, 2], [22, 3], [23, 4]], window_size=2, stride=2, tail="drop",
        ))
        self.assertEqual(windows[0].values, ((20, 1), (21, 2)))
        self.assertEqual(windows[1].values, ((22, 3), (23, 4)))

    def test_drop_excludes_incomplete_tail_without_padding(self):
        windows = self.windows(range(8), stride=2)
        self.assertEqual([(w.start, w.end) for w in windows], [(0, 3), (2, 5), (4, 7)])
        self.assertEqual(windows[-1].values, ((4,), (5,), (6,)))

    def test_reject_requires_last_window_to_reach_input_end(self):
        self.assertEqual(len(self.windows(range(7), stride=2, tail="reject")), 3)
        with self.assertRaisesRegex(ValueError, "incomplete tail"):
            self.windows(range(8), stride=2, tail="reject")
        self.assertEqual(len(self.windows(range(11), stride=4, tail="reject")), 3)

    def test_empty_and_short_inputs(self):
        self.assertEqual(self.windows([]), [])
        self.assertEqual(self.windows([], tail="reject"), [])
        self.assertEqual(self.windows([1, 2]), [])
        with self.assertRaises(ValueError):
            self.windows([1, 2], tail="reject")

    def test_invalid_options_fail_before_iteration(self):
        for name in ("window_size", "stride"):
            for value in (0, -1, True, 1.5, "3", None):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    iter_windows([[1]], **{"window_size": 1, "stride": 1, "tail": "drop", name: value})
        for offset in (-1, True, 1.5, "0"):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                iter_windows([[1]], window_size=1, stride=1, tail="drop", offset=offset)
        with self.assertRaises(ValueError):
            iter_windows([[1]], window_size=1, stride=1, tail="pad")

    def test_invalid_samples_fail_before_any_windows_are_returned(self):
        for samples in (
            None, "123", [1, 2], [[1], [2, 3]], [[]], ["12"], [[True]], [["1"]],
            {1, 2}, {0: [1]}, [{0: 1}], [{1, 2}], [bytearray(b"12")],
            [[float("nan")]], [[float("inf")]], [[10 ** 1000]], [[1 + 2j]],
        ):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                iter_windows(samples, window_size=1, stride=1, tail="drop")

    def test_snapshot_and_windows_cannot_mutate_each_other(self):
        source = [[1], [2], [3]]
        iterator = iter_windows(source, window_size=2, stride=1, tail="drop")
        source[1][0] = 99
        source.append([4])
        windows = list(iterator)
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0].values, ((1,), (2,)))
        self.assertEqual(windows[1].values, ((2,), (3,)))
        with self.assertRaises(TypeError):
            windows[0].values[1][0] = 10
        with self.assertRaises(FrozenInstanceError):
            windows[0].start = 99

    def test_offset_preserves_section_position_and_does_not_change_values(self):
        windows = self.windows([1, 2, 3, 4], offset=1000)
        self.assertEqual([(w.start, w.end) for w in windows], [(1000, 1003), (1001, 1004)])
        self.assertEqual(windows[0].values, ((1,), (2,), (3,)))
