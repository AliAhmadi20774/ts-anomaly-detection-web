import gzip
import io
from unittest import TestCase

from dat_imports.proto import current_pb2
from dat_imports.reader import DatReader
from sample_data.generate_sample_dat import make_payload, make_sensor_signals, make_signals


class SampleGeneratorTests(TestCase):
    def test_amplitude_changes_preserve_the_delay(self) -> None:
        signals = make_signals(64, 8, 16, step_level=2.0, sine_amplitude=3.0)
        self.assertEqual(signals["step"][16], 2.0)
        self.assertEqual(signals["sine"][4], 3.0)
        self.assertEqual(signals["sine_delayed"], [0.0] * 8 + signals["sine"][:-8])
        self.assertEqual(signals["step_delayed"], [0.0] * 8 + signals["step"][:-8])

    def test_each_test_has_four_aligned_signals_with_exact_delays(self) -> None:
        count = 64
        delay = 8
        waveforms = make_signals(count, delay, sine_period=16)
        payload = make_payload(
            "device1", "SN-001", ["test1", "test2"], "operator", "2026-11-20",
            count, delay, 16,
        )
        root = current_pb2.Array_ProtoDevice.FromString(payload)

        self.assertEqual(waveforms["step"], [0.0] * 16 + [1.0] * 48)
        for name in ("sine", "step"):
            self.assertEqual(waveforms[f"{name}_delayed"], [0.0] * delay + waveforms[name][:-delay])

        self.assertEqual([test.testName for test in root.items[0].testResult], ["test1", "test2"])
        for index, test in enumerate(root.items[0].testResult):
            self.assertEqual(
                {signal.name: list(signal.data) for signal in test.signals},
                make_sensor_signals(index, waveforms),
            )
            self.assertEqual(list(test.flatResultDataTable.ColumnNames), ["Signal", "RMS", "PeakAbs"])
            self.assertEqual(test.flatResultDataTable.ColumnCount, 3)
            self.assertEqual(len(test.flatResultDataTable.FlattendRows), 12)

        first = {signal.name: list(signal.data) for signal in root.items[0].testResult[0].signals}
        second = {signal.name: list(signal.data) for signal in root.items[0].testResult[1].signals}
        self.assertFalse(set(first) & set(second))
        self.assertEqual(first["pressure_kpa"][:delay], [100.0] * delay)
        self.assertEqual(second["flow_l_min"][:delay], [10.0] * delay)
        self.assertEqual(first["current_a"][:count // 4 + delay], [0.0] * (count // 4 + delay))
        self.assertEqual(second["speed_rpm"][-1], 1500.0)

        upload = io.BytesIO(gzip.compress(payload, mtime=0))
        upload.name = "sample.dat"
        upload.size = len(upload.getbuffer())
        _, preview = DatReader().read(upload)
        self.assertEqual(preview["format"], "current")
        self.assertEqual([len(test["signals"]) for test in preview["devices"][0]["tests"]], [4, 4])
        self.assertTrue(all(test["flat_result_table"]["valid_shape"] for test in preview["devices"][0]["tests"]))
