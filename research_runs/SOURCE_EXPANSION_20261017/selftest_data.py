"""Scientific data-path regression checks using only synthetic signals/bytes.

These checks do not download EEG, fit any model, or claim real cohort completion.
Run with: python selftest_data.py
"""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy.signal import sosfiltfilt

import p1_data as data


def fixture_file(path, *, bdf=False, unit=None, annotations=True, missing_channel=False):
    """Independent EDF/BDF serializer with known signed extrema and TAL events."""
    width, rate, count = (3, 1000, 10) if bdf else (2, 512, 10)
    names = list(data.CHANNELS18)
    if missing_channel:
        names[0] = "Unknown"
    physical = 375000 if bdf else 200
    minimum, maximum = -(2 ** (8 * width - 1)), 2 ** (8 * width - 1) - 1
    unit = unit or ("?V" if bdf else "uV")
    labels = names + (["BDF Annotations" if bdf else "EDF Annotations"] if annotations else [])
    ns = len(labels)
    def field(x, n):
        encoded = str(x).encode("latin-1")
        if len(encoded) > n:
            raise ValueError("fixture field overflow")
        return encoded.ljust(n, b" ")
    fixed = ((b"\xffBIOSEMI" if bdf else b"0       ") + field("synthetic", 80) + field("fixture", 80) +
             field("01.01.24", 8) + field("00.00.00", 8) + field(256 * (ns + 1), 8) +
             field("BDF+C" if bdf else "EDF+C", 44) + field(count, 8) + field(1, 8) + field(ns, 4))
    header = fixed
    for width_field, channel_values in [
        (16, labels), (80, [""] * ns), (8, [unit] * 18 + ([""] if annotations else [])),
        (8, [-physical] * 18 + ([-1] if annotations else [])),
        (8, [physical] * 18 + ([1] if annotations else [])),
        (8, [minimum] * ns), (8, [maximum] * ns), (80, [""] * ns),
        (8, [rate] * 18 + ([128] if annotations else [])), (32, [""] * ns),
    ]:
        header += b"".join(field(value, width_field) for value in channel_values)
    base = np.array([minimum, minimum + 1, -123, -1, 0, 1, maximum - 1, maximum], dtype=np.int64)
    digital = np.stack([np.resize(np.roll(base, i % len(base)), count * rate) for i in range(18)])
    with Path(path).open("wb") as stream:
        stream.write(header)
        for record in range(count):
            for channel in range(18):
                values = digital[channel, record * rate:(record + 1) * rate]
                # int.to_bytes supplies the reference sign representation.
                stream.write(b"".join(int(v).to_bytes(width, "little", signed=True) for v in values))
            if annotations:
                tal = f"+{record}\x14\x14\x00".encode()
                if record in (2, 4):
                    code = ("1" if record == 2 else "2") if bdf else ("769" if record == 2 else "770")
                    tal += f"+{record}\x140\x14{code}\x14\x00".encode().replace(b"\x140\x14", b"\x14")
                stream.write(tal.ljust(128 * width, b"\x00"))
    expected = (digital.astype(np.float64) - minimum) * (2 * physical / (maximum - minimum)) - physical
    return expected, rate


class DataPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = data.load_filter_bank()

    def test_frozen_forward_backward_equations(self):
        rng = np.random.default_rng(731)
        for rate in (250, 512, 1000):
            context = rng.normal(size=(18, rate * 6))
            for band in data.VIEWS:
                sos, zi = self.bank["arrays"][str(rate)][band]
                reference = sosfiltfilt(sos, context, axis=-1, padtype="odd", padlen=27)
                actual = data.explicit_sosfiltfilt(context, sos, zi)
                np.testing.assert_allclose(actual, reference, rtol=2e-13, atol=2e-13)

    def test_scale_invariant_trial_only_normalization(self):
        rng = np.random.default_rng(971)
        for rate in (250, 512, 1000):
            context = rng.normal(size=(18, rate * 6))
            original = context.copy()
            expected = data.transform_native_context(context, rate, self.bank)
            for multiplier in (1e-9, 1e6):
                actual = data.transform_native_context(context * multiplier, rate, self.bank)
                np.testing.assert_allclose(actual, expected, rtol=2e-6, atol=2e-6)
            np.testing.assert_array_equal(context, original)
            self.assertEqual(expected.shape, (3, 18, 320))
            self.assertEqual(expected.dtype, np.float32)
            self.assertAlmostEqual(float(np.mean(expected[0].astype(np.float64) ** 2)), 1.0, places=7)
            np.testing.assert_allclose(expected.mean(axis=-1), 0.0, atol=1e-7)
        with self.assertRaisesRegex(ValueError, "RMS"):
            data.transform_native_context(np.zeros((18, 1500)), 250, self.bank)

    def test_edf16_and_bdf24_signed_calibration_and_alignment(self):
        with tempfile.TemporaryDirectory(prefix="p1-data-test-") as folder:
            for bdf in (False, True):
                path = Path(folder) / ("synthetic.bdf" if bdf else "synthetic.edf")
                expected, rate = fixture_file(path, bdf=bdf)
                dataset = "yang" if bdf else "dreyer"
                with data.NativeReader(path, dataset, data.YANG_UNIT_CONVENTION) as reader:
                    # The 1.5-7.5 s context crosses physical record boundaries.
                    actual = reader.context(3 * rate)
                    np.testing.assert_array_equal(actual, expected[:, int(1.5 * rate):int(7.5 * rate)])
                    self.assertEqual(reader.header["sample_bytes"], 3 if bdf else 2)
                    if bdf:
                        self.assertTrue(all(row["rms_original_unit"] == "unresolved" for row in reader.unit_audit))
                    with self.assertRaisesRegex(ValueError, "complete"):
                        reader.context(0)

    def test_tal_cues_and_continuous_timestamps(self):
        with tempfile.TemporaryDirectory(prefix="p1-event-test-") as folder:
            path = Path(folder) / "synthetic.edf"
            fixture_file(path)
            events, audit = data.read_annotations(path, enforce_timekeeping=True)
            self.assertEqual([(r["onset"], r["description"]) for r in events], [(2.0, "769"), (4.0, "770")])
            self.assertTrue(audit["record_timekeeping_verified"])
            cues = data._validated_cues(events, {"769": 0, "770": 1}, 1)
            self.assertEqual(len(cues), 2)
            with self.assertRaisesRegex(ValueError, "marker counts"):
                data._validated_cues(events, {"769": 0, "770": 1}, 20)

    def test_missing_channels_and_ambiguous_units_fail(self):
        with tempfile.TemporaryDirectory(prefix="p1-invalid-test-") as folder:
            path = Path(folder) / "synthetic.bdf"
            fixture_file(path, bdf=True)
            with self.assertRaisesRegex(ValueError, "frozen Yang"):
                data.NativeReader(path, "yang")
            fixture_file(path, bdf=True, missing_channel=True)
            with self.assertRaisesRegex(ValueError, "genuine required"):
                data.NativeReader(path, "yang", data.YANG_UNIT_CONVENTION)
        self.assertNotIn(17, data.roster("dreyer"))
        self.assertNotIn(41, data.roster("dreyer"))
        self.assertEqual(len(data.roster("dreyer")), 85)
        self.assertEqual(data.subject_id("dreyer", 61), "B61")


if __name__ == "__main__":
    unittest.main(verbosity=2)
