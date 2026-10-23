"""Paper 1 expansion: authenticated native files -> fresh 18-channel inputs.

No downloads, model training, target statistics, fitted normalization, interpolation,
or historical-cache reuse occur here. Trial arrays are [trial, view, channel, time]
in the order broad/mu/beta, genuine CHANNELS18, 320 samples at 160 Hz. All three
datasets use CAR18 on each native six-second context, frozen Butterworth SOS/zi,
odd pad 27, resample_poly, and a fixed [0.5, 2.5) second analysis-anchor crop.
BNCI/Dreyer anchors are their operational MI cues. Yang's anchor is only an
analysis reference: raw marker + 1.5 s gives a marker-relative [2,4) s crop,
within both documented timing interpretations; actual MI phase is unresolved.
After
each view/channel is temporally centered, all three views are divided by that
trial's broad-view RMS. Output is dimensionless; no statistics cross trials.

EDF/BDF signals are decoded directly from integer samples and header calibration;
MNE SI scaling is deliberately not applied to these already decoded numbers.
Yang's damaged '?V' dimension is retained as unresolved physical numeric, with
exact audited 24-bit header values. A common positive voltage multiplier cancels
under the frozen trial RMS formula. The unit is never guessed to be microvolts.

Inputs: source_root/_download_manifest.json with
{dataset: ..., files: [{path: relative_path, sha256: ..., size: ...}]}.
The downloader verifies provider/archive provenance; this module verifies each
extracted file against that receipt before use. All session/class inventories
are mandatory. Missing data and changed bytes stop preparation, not drop trials.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid
from eligibility_policy import population, qualified_events, legacy_compatible

import numpy as np
import scipy
from scipy.io import loadmat
from scipy.signal import resample_poly, sosfilt


CHANNELS18 = (
    "Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1", "Cz",
    "C2", "C4", "C6", "CP3", "CP1", "CP2", "CP4", "Pz",
)
BNCI_CHANNELS22 = (
    "Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1", "Cz", "C2",
    "C4", "C6", "CP3", "CP1", "CPz", "CP2", "CP4", "P1", "Pz", "P2", "POz",
)
BANDS = {"broad": (8.0, 30.0), "mu": (8.0, 13.0), "beta": (13.0, 30.0)}
VIEWS = tuple(BANDS)
DATASET_NAMES = {"bnci": "BNCI2014_001", "yang": "Yang2025_2C", "dreyer": "Dreyer2023"}
NATIVE_RATES = {"bnci": 250, "yang": 1000, "dreyer": 512}
EXPECTED_TRIALS = {"bnci": 288, "yang": 600, "dreyer": 80}
COMMON_RATE = 160
N_TIMES = 320
PADLEN = 27
DEFAULT_FILTER_BANK = Path(__file__).resolve().parent / "config" / "filter_bank18.json"
YANG_UNIT_CONVENTION = "yang_v5_questionmark_V_scale_invariant"
NORMALIZATION = {
    "scope": "single_trial_only_no_cross_trial_or_subject_statistics",
    "center": "subtract_each_view_each_channel_temporal_mean_after_crop",
    "scale": "same_trial_broad_view_root_mean_square_over_18_channels_and_320_samples",
    "apply_scale_to": ["broad", "mu", "beta"],
    "epsilon": None,
    "zero_or_nonfinite_rms": "fail",
    "output_unit": "dimensionless",
}
TIMING = {
    "bnci": {
        "event_definition": "official_MAT_one_based_trial_start_converted_to_zero_based",
        "analysis_anchor_offset_from_event_seconds": 2.0,
        "analysis_anchor_definition": "verified_operational_MI_cue",
        "trigger_anchor_uncertain": False,
        "timing_policy": "verified_trial_start_plus_two_seconds_MI_cue",
        "event_relative_context_half_open_s": [0.5, 6.5],
        "event_relative_epoch_half_open_s": [2.5, 4.5],
    },
    "yang": {
        "event_definition": "raw_BDF_annotation_1_or_2",
        "analysis_anchor_offset_from_event_seconds": 1.5,
        "analysis_anchor_definition": "analysis_reference_only_not_verified_MI_onset",
        "trigger_anchor_uncertain": True,
        "timing_policy": "intersection_of_two_documented_interpretations",
        "event_relative_context_half_open_s": [0.0, 6.0],
        "event_relative_epoch_half_open_s": [2.0, 4.0],
        "documented_interpretations": {
            "MOABB_adapter": "MI_interval_1.5_to_5.5_seconds_after_marker",
            "author_archive_preprocessed_m": "epochs_0_to_4_seconds_after_marker_no_explicit_shift",
        },
        "limitation": "May represent a later MI phase; common absolute MI phase across datasets is not established",
    },
    "dreyer": {
        "event_definition": "native_EDF_annotation_769_or_770",
        "analysis_anchor_offset_from_event_seconds": 0.0,
        "analysis_anchor_definition": "verified_operational_MI_cue",
        "trigger_anchor_uncertain": False,
        "timing_policy": "native_left_right_class_cue",
        "event_relative_context_half_open_s": [-1.5, 4.5],
        "event_relative_epoch_half_open_s": [0.5, 2.5],
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def object_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_hash(value: np.ndarray) -> str:
    value = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(json.dumps({"shape": list(value.shape), "dtype": value.dtype.str}, sort_keys=True).encode())
    digest.update(memoryview(value).cast("B"))
    return digest.hexdigest()


def _integer_vector(value: Any, name: str) -> np.ndarray:
    value = np.asarray(value).reshape(-1)
    require(np.issubdtype(value.dtype, np.number) and not np.iscomplexobj(value), f"{name}: numeric integers required")
    require(np.isfinite(value).all() and np.equal(value, np.floor(value)).all(), f"{name}: nonfinite/noninteger")
    require(np.all((value >= -(2**63)) & (value < 2**63)), f"{name}: integer overflow")
    return value.astype(np.int64)


def _grid(value: float, name: str, tolerance: float = 1e-7) -> int:
    require(np.isfinite(value) and abs(value - round(value)) <= tolerance, f"{name}: not on native sample grid")
    return int(round(value))


def _dataset_key(name: str) -> str:
    aliases = {**{key.lower(): key for key in DATASET_NAMES},
               **{value.lower(): key for key, value in DATASET_NAMES.items()},
               "yang2025": "yang"}
    require(str(name).lower() in aliases, f"Unknown dataset: {name}")
    return aliases[str(name).lower()]


def _subject_number(dataset: str, value: int | str) -> int:
    if isinstance(value, str):
        matched = re.fullmatch(r"(?:BNCI|Yang2C|Dreyer|sub-)?([ABC]?)(\d+)", value, re.IGNORECASE)
        require(matched is not None, f"Invalid subject identity: {value}")
        number = int(matched.group(2))
        if matched.group(1):
            require(dataset == "dreyer" and subject_id(dataset, number)[-3:].upper() == value[-3:].upper(),
                    f"Dreyer subgroup/number mismatch: {value}")
    else:
        require(isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)), "Integer subject required")
        number = int(value)
    limit = {"bnci": 9, "yang": 51, "dreyer": 87}[dataset]
    require(1 <= number <= limit, f"Subject outside {dataset} roster: {number}")
    return number


def subject_id(dataset: str, number: int) -> str:
    dataset = _dataset_key(dataset)
    if dataset == "dreyer":
        return ("A" if number <= 60 else "B" if number <= 81 else "C") + f"{number:02d}"
    return ("BNCI" if dataset == "bnci" else "Yang2C") + f"{number:03d}"


def roster(dataset: str) -> list[int]:
    dataset = _dataset_key(dataset)
    return [number for number in range(1, {"bnci": 9, "yang": 51, "dreyer": 87}[dataset] + 1)
            if dataset != "dreyer" or number not in (17, 41)]


class VerifiedFiles:
    """Bind each native file to the current downloader's immutable file receipt."""

    def __init__(self, root: str | Path, manifest_path: str | Path | None = None):
        self.root = Path(root).resolve(strict=True)
        self.manifest_path = Path(manifest_path) if manifest_path else self.root / "_download_manifest.json"
        require(self.manifest_path.is_file(), f"Missing downloader manifest: {self.manifest_path}")
        self.manifest_sha256 = file_hash(self.manifest_path)
        obj = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        records = obj if isinstance(obj, list) else obj.get("files", [])
        require(isinstance(records, list) and records, "Nonempty native-file manifest required")
        self.records: dict[str, dict] = {}
        for row in records:
            relative = str(row.get("path", ""))
            p = Path(relative)
            require(relative and not p.is_absolute() and ".." not in p.parts, "Manifest paths must be relative, nontraversing")
            require(relative not in self.records, f"Duplicate manifest path: {relative}")
            checksum = row.get("sha256", row.get("checksum"))
            size = row.get("size", row.get("bytes", row.get("size_bytes")))
            require(isinstance(checksum, str) and re.fullmatch("[0-9a-f]{64}", checksum), f"Missing SHA256: {relative}")
            require(type(size) is int and size > 0, f"Missing positive byte count: {relative}")
            self.records[relative] = {"path": relative, "sha256": checksum, "size": size}
        self.used: dict[str, dict] = {}

    def find(self, *, relative: str | None = None, basename: str | None = None) -> Path:
        require((relative is None) != (basename is None), "Specify exactly one file identity")
        names = ([name for name in self.records if name == relative or name.endswith("/" + relative)] if relative is not None else
                 [name for name in self.records if Path(name).name == basename])
        require(len(names) == 1 and names[0] in self.records, f"Expected one authenticated file: {relative or basename}")
        name = names[0]
        path = self.root / name
        require(path.is_file() and path.resolve().is_relative_to(self.root), f"Raw file missing/outside root: {name}")
        require(not any(p.is_symlink() for p in [path, *path.parents] if p != self.root.parent),
                f"Raw symlink path not permitted: {name}")
        expected = self.records[name]
        require(path.stat().st_size == expected["size"] and file_hash(path) == expected["sha256"],
                f"Raw file differs from downloader manifest: {name}")
        self.used[name] = expected
        return path

    def recheck_used(self) -> None:
        require(file_hash(self.manifest_path) == self.manifest_sha256, "Downloader manifest changed during preparation")
        for row in self.used.values():
            path = self.root / row["path"]
            require(path.stat().st_size == row["size"] and file_hash(path) == row["sha256"],
                    f"Raw bytes changed during preparation: {row['path']}")


def load_filter_bank(path: str | Path = DEFAULT_FILTER_BANK) -> dict:
    path = Path(path)
    bank = json.loads(path.read_text(encoding="utf-8"))
    expected = {"schema_version": 1, "channels": list(CHANNELS18), "view_order": list(VIEWS),
                "rate_hz": COMMON_RATE, "context_half_open_s": [-1.5, 4.5],
                "crop_half_open_s": [0.5, 2.5], "padtype": "odd", "padlen": PADLEN,
                "reference": "common_average_actual18", "prototype_order": 4,
                "normalization": NORMALIZATION,
                "time_axis": "relative_to_declared_dataset_analysis_anchor",
                "dataset_timing": TIMING,
                "resampling": {"method": "scipy.signal.resample_poly", "window": ["kaiser", 5.0],
                               "padtype": "constant", "cval": 0.0}}
    for key, value in expected.items():
        require(bank.get(key) == value, f"Frozen processing contract mismatch: {key}")
    require(set(bank.get("rates", {})) == {"250", "512", "1000"}, "Frozen native filter rates incomplete")
    require(bank.get("numpy_version") == np.__version__ and bank.get("scipy_version") == scipy.__version__,
            "Preprocessing NumPy/SciPy versions differ from frozen coefficient/runtime profile")
    arrays = {}
    for rate, bands in bank["rates"].items():
        require(set(bands) == set(VIEWS), f"Frozen filter bands incomplete: {rate}")
        arrays[rate] = {}
        for band, entry in bands.items():
            sos = np.array([[float.fromhex(v) for v in row] for row in entry["sos_hex"]], dtype=np.float64)
            zi = np.array([[float.fromhex(v) for v in row] for row in entry["zi_hex"]], dtype=np.float64)
            require(sos.shape == (4, 6) and zi.shape == (4, 2), "Invalid frozen SOS/zi shape")
            require(np.isfinite(sos).all() and np.isfinite(zi).all() and np.all(sos[:, 3] == 1), "Invalid SOS/zi values")
            require(array_hash(sos) == entry["sos_sha256"] and array_hash(zi) == entry["zi_sha256"], "Frozen SOS/zi hash mismatch")
            arrays[rate][band] = (sos, zi)
    return {"contract": bank, "arrays": arrays, "sha256": file_hash(path)}


def explicit_sosfiltfilt(context: np.ndarray, sos: np.ndarray, zi: np.ndarray) -> np.ndarray:
    """Public scipy.sosfilt equations with fixed state; no LAPACK state recompute."""
    require(context.ndim == 2 and context.shape[-1] > PADLEN, "Context too short for fixed odd padding")
    left = 2.0 * context[:, :1] - context[:, PADLEN:0:-1]
    right = 2.0 * context[:, -1:] - context[:, -2:-PADLEN - 2:-1]
    extended = np.concatenate((left, context, right), axis=-1)
    state = zi[:, None, :]
    filtered, _ = sosfilt(sos, extended, axis=-1, zi=state * extended[None, :, :1])
    filtered, _ = sosfilt(sos, filtered[:, ::-1], axis=-1, zi=state * filtered[None, :, -1:])
    return filtered[:, ::-1][:, PADLEN:-PADLEN]


def transform_native_context(context_native: np.ndarray, sfreq: int | float, bank: dict,
                             *, return_audit: bool = False):
    rate = _grid(float(sfreq), "native sampling rate")
    require(str(rate) in bank["arrays"], f"Unregistered native sampling rate: {rate}")
    require(np.asarray(context_native).shape == (18, 6 * rate), "Complete native [18,6*sfreq] context required")
    context = np.array(context_native, dtype=np.float64, copy=True)
    require(np.isfinite(context).all(), "Nonfinite native retained context")
    context -= context.mean(axis=0, keepdims=True)
    ratio = Fraction(COMMON_RATE, rate)
    result = []
    for band in VIEWS:
        sos, zi = bank["arrays"][str(rate)][band]
        filtered = explicit_sosfiltfilt(context, sos, zi)
        resampled = resample_poly(filtered, ratio.numerator, ratio.denominator, axis=-1,
                                  window=("kaiser", 5.0), padtype="constant", cval=0.0)
        require(resampled.shape == (18, 960), "Resampled complete context shape mismatch")
        result.append(resampled[:, 320:640])
    stacked = np.stack(result)
    stacked -= stacked.mean(axis=-1, keepdims=True)
    broad_rms = float(np.sqrt(np.mean(stacked[0] ** 2)))
    require(np.isfinite(broad_rms) and broad_rms > 0, "Zero/nonfinite native broad-view RMS; no arbitrary epsilon is used")
    output = np.ascontiguousarray(stacked / broad_rms, dtype=np.float32)
    require(output.shape == (3, 18, N_TIMES) and np.isfinite(output).all(), "Invalid processed trial")
    audit = {"trial_broad_rms_before_normalization": broad_rms,
             "trial_normalization_uses_other_trials": False}
    return (output, audit) if return_audit else output


def _unit_factor(unit: str) -> float:
    # U+00B5 and U+03BC both denote micro; EDF stores Latin-1 where applicable.
    normalized = unit.strip().replace("µ", "u").replace("μ", "u")
    factors = {"V": 1e6, "mV": 1e3, "uV": 1.0, "nV": 1e-3}
    require(normalized in factors, f"Unqualified native voltage unit: {unit!r}")
    return factors[normalized]


def parse_edf_header(path: str | Path) -> dict:
    """Read EDF/BDF fixed header and enforce complete, equally timed records."""
    path = Path(path)
    with path.open("rb") as stream:
        fixed = stream.read(256)
        require(len(fixed) == 256, "Truncated EDF/BDF fixed header")
        is_bdf = fixed[:8] == b"\xffBIOSEMI"
        require(is_bdf or fixed[:8].strip() == b"0", "Unsupported native EDF/BDF version")
        width = 3 if is_bdf else 2
        ns = int(fixed[252:256])
        header_bytes = int(fixed[184:192])
        require(ns > 0 and header_bytes == 256 * (ns + 1), "Invalid native EDF/BDF header length")
        signal_headers = stream.read(header_bytes - 256)
    require(len(signal_headers) == header_bytes - 256, "Truncated signal headers")
    definitions = [("label", 16), ("transducer", 80), ("unit", 8), ("physical_min", 8),
                   ("physical_max", 8), ("digital_min", 8), ("digital_max", 8),
                   ("prefilter", 80), ("samples_per_record", 8), ("reserved", 32)]
    fields, pos = {}, 0
    for name, length in definitions:
        fields[name] = [signal_headers[pos + i * length:pos + (i + 1) * length].decode("latin-1").strip()
                        for i in range(ns)]
        pos += length * ns
    records, duration = int(fixed[236:244]), float(fixed[244:252])
    require(records > 0 and np.isfinite(duration) and duration > 0, "Positive native records/duration required")
    channels = []
    for i in range(ns):
        row = {name: values[i] for name, values in fields.items()}
        for key in ("physical_min", "physical_max", "digital_min", "digital_max"):
            row[key] = float(row[key])
        row["samples_per_record"] = int(row["samples_per_record"])
        require(row["samples_per_record"] > 0, "Nonpositive samples per native record")
        row["sfreq"] = row["samples_per_record"] / duration
        channels.append(row)
    record_bytes = width * sum(c["samples_per_record"] for c in channels)
    require(header_bytes + records * record_bytes == path.stat().st_size, "Native record/file byte count mismatch")
    reserved = fixed[192:236].decode("latin-1").strip()
    require("+D" not in reserved, "Discontinuous EDF/BDF timing is not implemented")
    return {"format": "BDF" if is_bdf else "EDF", "sample_bytes": width,
            "header_bytes": header_bytes, "records": records, "record_duration": duration,
            "record_bytes": record_bytes, "start_date_time": fixed[168:184].decode("latin-1"),
            "reserved": reserved, "channels": channels,
            "fixed_header_sha256": hashlib.sha256(fixed + signal_headers).hexdigest()}


def read_annotations(path: str | Path, *, enforce_timekeeping: bool = False) -> tuple[list[dict], dict]:
    """Read standard EDF+/BDF+ TAL bytes, including separate Neuracle evt.bdf."""
    header = parse_edf_header(path)
    channels = header["channels"]
    indices = [i for i, c in enumerate(channels) if c["label"] in ("EDF Annotations", "BDF Annotations")]
    require(len(indices) == 1, "Exactly one native EDF/BDF annotation channel required")
    index = indices[0]
    offsets = np.r_[0, np.cumsum([c["samples_per_record"] * header["sample_bytes"] for c in channels])]
    events, stamps = [], []
    with Path(path).open("rb") as stream:
        for record in range(header["records"]):
            stream.seek(header["header_bytes"] + record * header["record_bytes"] + int(offsets[index]))
            payload = stream.read(int(offsets[index + 1] - offsets[index]))
            require(len(payload) == offsets[index + 1] - offsets[index], "Truncated native annotations")
            record_stamp = None
            for tal in payload.split(b"\x00"):
                if not tal:
                    continue
                require(b"\x14" in tal, "Malformed native annotation TAL")
                parts = tal.decode("utf-8", errors="strict").split("\x14")
                timing = parts[0].split("\x15")
                onset = float(timing[0])
                duration = float(timing[1]) if len(timing) == 2 and timing[1] else 0.0
                require(np.isfinite(onset) and np.isfinite(duration) and duration >= 0, "Invalid annotation time")
                if record_stamp is None and not any(parts[1:]):
                    record_stamp = onset
                for description in parts[1:]:
                    if description:
                        events.append({"onset": onset, "duration": duration, "description": description})
            if enforce_timekeeping:
                require(record_stamp is not None and
                        abs(record_stamp - record * header["record_duration"]) <= 0.5 / 512 + 1e-10,
                        "EDF continuous record clock mismatch")
            stamps.append(record_stamp)
    return events, {"header_sha256": header["fixed_header_sha256"],
                    "start_date_time": header["start_date_time"], "records": header["records"],
                    "record_timekeeping_verified": enforce_timekeeping,
                    "annotation_counts": dict(Counter(row["description"] for row in events))}


class NativeReader:
    """Read real channel contexts directly from calibrated 16-/24-bit records."""

    def __init__(self, path: str | Path, dataset: str, yang_unit_policy: str | None = None):
        self.path, self.dataset = Path(path), _dataset_key(dataset)
        self.header = parse_edf_header(path)
        channels = self.header["channels"]
        names = [c["label"].upper() for c in channels]
        require(len(names) == len(set(names)), "Duplicate native channel labels")
        require(all(name.upper() in names for name in CHANNELS18), "A genuine required channel is absent")
        self.indices = [names.index(name.upper()) for name in CHANNELS18]
        self.selected = [channels[i] for i in self.indices]
        self.sfreq = NATIVE_RATES[self.dataset]
        require(all(c["sfreq"] == self.sfreq for c in self.selected), "Native selected channel rates differ from contract")
        self.samples_per_record = self.selected[0]["samples_per_record"]
        require(all(c["samples_per_record"] == self.samples_per_record for c in self.selected), "Selected channel record sizes differ")
        self.n_samples = self.header["records"] * self.samples_per_record
        self.factors, self.unit_audit = [], []
        if self.dataset == "yang":
            require(len({c["unit"] for c in self.selected}) == 1,
                    "Yang scale invariance requires one common native voltage dimension across all 18 channels")
        for name, c in zip(CHANNELS18, self.selected):
            physical = (c["physical_min"], c["physical_max"])
            digital = (c["digital_min"], c["digital_max"])
            require(np.isfinite(physical + digital).all() and physical[0] < physical[1] and digital[0] < digital[1],
                    f"Invalid header calibration: {name}")
            require(all(float(d).is_integer() for d in digital), f"Noninteger native digital range: {name}")
            require(digital[0] >= -(2 ** (8 * self.header["sample_bytes"] - 1)) and
                    digital[1] <= 2 ** (8 * self.header["sample_bytes"] - 1) - 1, "Digital range exceeds sample representation")
            declared = c["unit"]
            if declared == "?V":
                require(self.dataset == "yang" and yang_unit_policy == YANG_UNIT_CONVENTION and
                        self.header["format"] == "BDF" and physical == (-375000.0, 375000.0) and
                        digital == (-8388608.0, 8388607.0) and self.sfreq == 1000,
                        "Ambiguous '?V' header requires the exact frozen Yang v5 analysis convention")
                factor, interpretation = 1.0, YANG_UNIT_CONVENTION
                verified = False
            else:
                factor, interpretation, verified = _unit_factor(declared), "explicit_header_voltage_dimension", True
            self.factors.append(factor)
            self.unit_audit.append({"channel": name, "declared_header_unit": declared,
                                    "physical_min": physical[0], "physical_max": physical[1],
                                    "digital_min": digital[0], "digital_max": digital[1],
                                    "physical_to_analysis_numeric_factor": factor, "interpretation": interpretation,
                                    "rms_original_unit": "unresolved" if declared == "?V" else "microvolts",
                                    "analysis_unit": "dimensionless_after_same_trial_broad_RMS",
                                    "header_voltage_dimension_unambiguous": verified,
                                    "original_instrument_calibration_independently_verified": False})
        self.offsets = np.r_[0, np.cumsum([c["samples_per_record"] * self.header["sample_bytes"] for c in channels])]
        self.buffer = np.memmap(self.path, mode="r", dtype=np.uint8, offset=self.header["header_bytes"],
                                shape=(self.header["records"], self.header["record_bytes"]))

    def close(self) -> None:
        if getattr(self, "buffer", None) is not None:
            self.buffer._mmap.close()
            self.buffer = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def context(self, analysis_anchor: int) -> np.ndarray:
        start = analysis_anchor - _grid(1.5 * self.sfreq, "context start offset")
        stop = analysis_anchor + _grid(4.5 * self.sfreq, "context stop offset")
        require(start >= 0 and stop <= self.n_samples, "Trial lacks the complete real six-second context")
        first = start // self.samples_per_record
        last = (stop + self.samples_per_record - 1) // self.samples_per_record
        left = start - first * self.samples_per_record
        right = left + stop - start
        output = []
        for index, c, factor in zip(self.indices, self.selected, self.factors):
            octets = np.ascontiguousarray(self.buffer[first:last, int(self.offsets[index]):int(self.offsets[index + 1])])
            if self.header["sample_bytes"] == 2:
                digital = np.frombuffer(octets, dtype="<i2").astype(np.int32)
            else:
                values = octets.reshape(-1, 3).astype(np.int32)
                digital = values[:, 0] | (values[:, 1] << 8) | (values[:, 2] << 16)
                digital = (digital ^ 0x800000) - 0x800000
            digital = digital[left:right]
            require(digital.size == 6 * self.sfreq and np.all((digital >= c["digital_min"]) & (digital <= c["digital_max"])),
                    "Truncated/out-of-range native integer context")
            scale = (c["physical_max"] - c["physical_min"]) / (c["digital_max"] - c["digital_min"])
            physical_numeric = ((digital.astype(np.float64) - c["digital_min"]) * scale + c["physical_min"]) * factor
            output.append(physical_numeric)
        result = np.stack(output)
        require(np.isfinite(result).all(), "Nonfinite calibrated native context")
        return result


@dataclass
class SubjectData:
    X: np.ndarray
    y: np.ndarray
    metadata: list[dict]
    audit: dict


def _row(dataset: str, person: int, session: str, run: str, ordinal: int, y: int,
         event_sample: int, analysis_anchor: int, sfreq: int, source_path: str, **extra) -> dict:
    sid = subject_id(dataset, person)
    result = {"dataset": DATASET_NAMES[dataset], "subject": sid, "provider_subject": person,
            "session": session, "run": run, "trial_id": f"{sid}/{session}/{run}/trial-{ordinal:03d}",
            "trial_ordinal": ordinal, "y": y, "label": ("left_hand", "right_hand")[y],
            "event_sample": event_sample, "analysis_anchor_sample": analysis_anchor, "native_rate_hz": sfreq,
            "context_native_start": analysis_anchor - _grid(1.5 * sfreq, "context offset"),
            "context_native_stop": analysis_anchor + _grid(4.5 * sfreq, "context offset"),
            "trigger_anchor_uncertain": TIMING[dataset]["trigger_anchor_uncertain"],
            "timing_policy": TIMING[dataset]["timing_policy"],
            "event_relative_context_half_open_s": TIMING[dataset]["event_relative_context_half_open_s"],
            "event_relative_epoch_half_open_s": TIMING[dataset]["event_relative_epoch_half_open_s"],
            "source_path": source_path, **extra}
    if dataset != "yang":
        result["mi_onset_sample"] = analysis_anchor
    return result


def _finish(dataset: str, person: int, epochs: list, rows: list[dict], run_audits: list[dict],
            verified: VerifiedFiles, bank: dict) -> SubjectData:
    expected_n, expected_counts = population(dataset, person)
    require(len(rows) == expected_n and len({r["trial_id"] for r in rows}) == len(rows),
            f"{dataset}/{person}: incomplete or duplicate retained trial inventory")
    require(Counter(r["y"] for r in rows) == expected_counts, "Subject left/right counts changed")
    X = np.ascontiguousarray(np.stack(epochs), dtype=np.float32)
    y = np.array([row["y"] for row in rows], dtype=np.int64)
    require(X.shape == (expected_n, 3, 18, N_TIMES) and np.isfinite(X).all(), "Full processed subject failed audit")
    verified.recheck_used()
    audit = {"schema_version": 1, "status": "PASS_FRESH18_SUBJECT_INPUTS", "dataset": DATASET_NAMES[dataset],
             "subject": subject_id(dataset, person), "provider_subject": person, "n_trials": len(rows),
             "class_counts": {"left_hand": expected_counts[0], "right_hand": expected_counts[1]},
             "shape": list(X.shape), "dtype": "float32", "units": "dimensionless",
             "view_order": list(VIEWS), "channels": list(CHANNELS18), "sample_rate_hz": COMMON_RATE,
             "filter_bank_sha256": bank["sha256"], "data_module_sha256": file_hash(__file__),
             "downloader_manifest_sha256": verified.manifest_sha256,
             "raw_files": sorted(verified.used.values(), key=lambda row: row["path"]),
             "run_audit": run_audits, "metadata_sha256": object_hash(rows),
             "X_sha256": array_hash(X), "y_sha256": array_hash(y),
             "numpy_version": np.__version__, "scipy_version": scipy.__version__,
             "normalization": NORMALIZATION,
             "timing": TIMING[dataset],
             "target_fits": 0, "fitted_preprocessing": False, "target_scores_computed": False,
             "excluded_trials": ([{"session": r["session"], **e} for r in run_audits for e in r["events"]["eligibility"]["unknown_events"]] if dataset == "yang" else []), "old_19_or_21_channel_results_reused": False,
             "evidence_class": "EXPOSURE_UNCONFIRMED_EXPLORATORY" if dataset == "dreyer" else "SOURCE_ONLY"}
    return SubjectData(X, y, rows, audit)


def load_bnci_subject(subject: int | str, source_root: str | Path, bank: dict,
                      manifest_path: str | Path | None = None) -> SubjectData:
    person = _subject_number("bnci", subject)
    verified = VerifiedFiles(source_root, manifest_path)
    epochs, rows, audits = [], [], []
    indices = [BNCI_CHANNELS22.index(name) for name in CHANNELS18]
    for suffix, session in (("T", "0train"), ("E", "1test")):
        path = verified.find(basename=f"A{person:02d}{suffix}.mat")
        runs = loadmat(path, variable_names=["data"], simplify_cells=True).get("data")
        runs = [runs] if isinstance(runs, dict) else np.asarray(runs, dtype=object).reshape(-1).tolist()
        require(all(isinstance(run, dict) for run in runs), "BNCI original MATLAB run structs required")
        active = [run for run in runs if np.asarray(run.get("trial", [])).size]
        require(len(active) == 6, "BNCI must contain six original four-class MI runs")
        for ri, run in enumerate(active, 1):
            native = np.asarray(run["X"])
            require(native.ndim == 2 and native.shape[1] == 25 and float(run["fs"]) == 250 and
                    np.issubdtype(native.dtype, np.number) and not np.iscomplexobj(native) and np.isfinite(native).all(),
                    "BNCI native 250 Hz/22 EEG+3 EOG numeric schema changed")
            trials = _integer_vector(run["trial"], "BNCI trial samples")
            labels = _integer_vector(run["y"], "BNCI label codes")
            flags = _integer_vector(run["artifacts"], "BNCI artifact flags")
            require(len(trials) == len(labels) == len(flags) == 48 and Counter(labels.tolist()) == {1: 12, 2: 12, 3: 12, 4: 12},
                    "BNCI complete original four-class inventory changed")
            require(np.isin(flags, (0, 1)).all() and np.all(trials >= 1) and np.all(np.diff(trials) > 0),
                    "BNCI native flags/sample ordering invalid")
            signal = native[:, indices].T
            require(np.all(np.ptp(signal, axis=1) > 0), "Flat required BNCI channel")
            for ordinal, (start, label, flag) in enumerate(zip(trials, labels, flags), 1):
                mi_sample = int(start) - 1 + 500
                lo, hi = mi_sample - 375, mi_sample + 1125
                require(lo >= 0 and hi <= signal.shape[1], "BNCI original trial lacks full context")
                if label not in (1, 2):
                    continue  # Protocol task restriction, not a quality/performance exclusion.
                context = signal[:, lo:hi]
                transformed, norm_audit = transform_native_context(context, 250, bank, return_audit=True)
                epochs.append(transformed)
                rows.append(_row("bnci", person, session, f"run-{ri:02d}", ordinal, int(label) - 1,
                                 int(start) - 1, mi_sample, 250, path.relative_to(verified.root).as_posix(),
                                 provider_artifact_flag=bool(flag), cue_to_mi_onset_seconds=0.0,
                                 trial_start_to_mi_onset_seconds=2.0,
                                 rms_original_unit="microvolts_analysis_convention", **norm_audit))
            audits.append({"session": session, "run": f"run-{ri:02d}", "n_original_trials": 48,
                           "n_binary_trials": 24, "provider_artifact_flags_included": int(np.sum(flags[np.isin(labels, (1, 2))])),
                           "native_numeric_unit_policy": "BNCI_official_MAT_native_numeric_microvolt_convention",
                           "original_instrument_calibration_independently_verified": False})
    return _finish("bnci", person, epochs, rows, audits, verified, bank)


def _validated_cues(events: list[dict], mapping: dict[str, int], expected_each: int) -> list[dict]:
    cues = [row for row in events if row["description"] in mapping]
    require(Counter(row["description"] for row in cues) == {key: expected_each for key in mapping},
            f"Native task marker counts changed: expected {expected_each} each of {list(mapping)}")
    require(all(cues[i]["onset"] < cues[i + 1]["onset"] for i in range(len(cues) - 1)),
            "Nonordered/duplicate native task cue onsets")
    return cues


def load_yang_subject(subject: int | str, source_root: str | Path, bank: dict,
                      manifest_path: str | Path | None = None,
                      yang_unit_policy: str | None = None) -> SubjectData:
    person = _subject_number("yang", subject)
    verified = VerifiedFiles(source_root, manifest_path)
    epochs, rows, audits = [], [], []
    for si in range(1, 4):
        base = f"sourcedata/2C dataset/sub-{person:03d}/ses-{si:02d}/eeg"
        path = verified.find(relative=base + "/data.bdf")
        events_path = verified.find(relative=base + "/evt.bdf")
        events, event_audit = read_annotations(events_path)
        cues, event_audit["eligibility"] = qualified_events(person, si, events,
            verified.used[events_path.relative_to(verified.root).as_posix()])
        with NativeReader(path, "yang", yang_unit_policy) as reader:
            from yang_clock_policy import validate_yang_clock
            event_audit["clock_policy"] = validate_yang_clock(
                person, si, reader.header["start_date_time"], event_audit["start_date_time"],
                verified.used[path.relative_to(verified.root).as_posix()],
                verified.used[events_path.relative_to(verified.root).as_posix()],
                reader.header["fixed_header_sha256"], event_audit["header_sha256"])
            running_min, running_max = np.full(18, np.inf), np.full(18, -np.inf)
            for ordinal, cue in enumerate(cues, 1):
                event_sample = _grid(cue["onset"] * 1000, "Yang cue", tolerance=0.5 + 1e-9)
                analysis_anchor = event_sample + 1500  # Analysis reference; marker semantics remain unresolved.
                context = reader.context(analysis_anchor)
                running_min = np.minimum(running_min, context.min(axis=1))
                running_max = np.maximum(running_max, context.max(axis=1))
                transformed, norm_audit = transform_native_context(context, 1000, bank, return_audit=True)
                epochs.append(transformed)
                rows.append(_row("yang", person, f"ses-{si:02d}", "continuous", ordinal,
                                 int(cue["description"]) - 1, event_sample, analysis_anchor, 1000,
                                 path.relative_to(verified.root).as_posix(),
                                 provider_event_code=cue["description"], event_onset_seconds=cue["onset"],
                                 raw_event_to_analysis_anchor_seconds=1.5, block=cue["native_segment"],
                                 native_event_index=cue["native_event_index"],
                                 native_observed_task_ordinal=cue["native_observed_task_ordinal"],
                                 trial_ordinal_semantics="retained_order_not_reconstructed_planned_trial",
                                 rms_original_unit="unresolved" if reader.selected[0]["unit"] == "?V" else "microvolts",
                                 **norm_audit))
            require(np.all(running_max > running_min), "Flat required Yang channel across retained native contexts")
            # Native marker-delimited segments were checked and audited by qualified_events.
            audits.append({"session": f"ses-{si:02d}", "n_binary_trials": len(cues), "timing": TIMING["yang"],
                           "header": reader.header, "unit_audit": reader.unit_audit, "events": event_audit,
                           "retained_context_dynamic_range_original_numeric": (running_max - running_min).tolist()})
    return _finish("yang", person, epochs, rows, audits, verified, bank)


def load_dreyer_subject(subject: int | str, source_root: str | Path, bank: dict,
                        manifest_path: str | Path | None = None) -> SubjectData:
    person = _subject_number("dreyer", subject)
    require(person not in (17, 41), "Dreyer provider montage exclusions A17/A41 remain excluded")
    verified = VerifiedFiles(source_root, manifest_path)
    declared = set()
    pattern = re.compile(r"sourcedata/sub-(\d{2})/eeg/sub-\1_task-(R[12]acquisition)_eeg\.edf\Z")
    for relative in verified.records:
        match = pattern.fullmatch(relative)
        if match:
            declared.add((int(match.group(1)), match.group(2)))
    require(declared == {(p, run) for p in range(1, 88) for run in ("R1acquisition", "R2acquisition")},
            "Dreyer downloader receipt must cover all 174 acquisition objects")
    epochs, rows, audits = [], [], []
    for run in ("R1acquisition", "R2acquisition"):
        relative = f"sourcedata/sub-{person:02d}/eeg/sub-{person:02d}_task-{run}_eeg.edf"
        path = verified.find(relative=relative)
        events, event_audit = read_annotations(path, enforce_timekeeping=True)
        cues = _validated_cues(events, {"769": 0, "770": 1}, 20)
        with NativeReader(path, "dreyer") as reader:
            require(reader.header["format"] == "EDF" and "EDF+C" in reader.header["reserved"], "Dreyer continuous acquisition EDF+C required")
            running_min, running_max = np.full(18, np.inf), np.full(18, -np.inf)
            for ordinal, cue in enumerate(cues, 1):
                mi_sample = _grid(cue["onset"] * 512, "Dreyer cue", tolerance=0.5 + 1e-9)
                context = reader.context(mi_sample)
                running_min = np.minimum(running_min, context.min(axis=1))
                running_max = np.maximum(running_max, context.max(axis=1))
                transformed, norm_audit = transform_native_context(context, 512, bank, return_audit=True)
                epochs.append(transformed)
                rows.append(_row("dreyer", person, "acquisition", run, ordinal,
                                 int(cue["description"]) - 769, mi_sample, mi_sample, 512, relative,
                                 provider_event_code=cue["description"], event_onset_seconds=cue["onset"],
                                 cue_to_mi_onset_seconds=0.0,
                                 historical_event_id=f"{subject_id('dreyer', person)}_{run}_cue_{ordinal:02d}",
                                 rms_original_unit="microvolts", **norm_audit))
            require(np.all(running_max > running_min), "Flat required Dreyer channel across retained native contexts")
            audits.append({"run": run, "n_binary_trials": 40, "header": reader.header,
                           "unit_audit": reader.unit_audit, "events": event_audit,
                           "retained_context_dynamic_range_uv": (running_max - running_min).tolist()})
    return _finish("dreyer", person, epochs, rows, audits, verified, bank)


def build_subject_npz(dataset: str, subject_id: int | str, source_root: str | Path,
                      output_path: str | Path, filter_bank_json: str | Path = DEFAULT_FILTER_BANK,
                      manifest_path: str | Path | None = None,
                      yang_unit_policy: str | None = None) -> dict:
    """Prepare one authenticated person; existing outputs are never trusted blindly."""
    dataset = _dataset_key(dataset)
    bank = load_filter_bank(filter_bank_json)
    loaders = {"bnci": load_bnci_subject, "yang": load_yang_subject, "dreyer": load_dreyer_subject}
    kwargs = {"yang_unit_policy": yang_unit_policy} if dataset == "yang" else {}
    data = loaders[dataset](subject_id, source_root, bank, manifest_path=manifest_path, **kwargs)
    output = Path(output_path)
    require(output.suffix == ".npz", "Processed person output must end in .npz")
    output.parent.mkdir(parents=True, exist_ok=True)
    arrays = {"X": data.X, "y": data.y,
              "metadata_json": np.array([canonical_json(row) for row in data.metadata]),
              "audit_json": np.array(canonical_json(data.audit))}
    for key in ("dataset", "subject", "session", "run", "trial_id"):
        arrays[key] = np.array([row[key] for row in data.metadata])
    temporary = output.with_name(output.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("wb") as stream:
            np.savez_compressed(stream, **arrays)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    receipt = {**data.audit, "npz_path": str(output), "npz_sha256": file_hash(output), "npz_bytes": output.stat().st_size}
    receipt_path = output.with_suffix(".audit.json")
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def verify_subject_npz(path: str | Path, *, filter_bank_json: str | Path = DEFAULT_FILTER_BANK) -> dict:
    """Validate a cache without allowing pickled data or relying on a success flag."""
    with np.load(path, allow_pickle=False) as data:
        audit = json.loads(data["audit_json"].item())
        rows = [json.loads(row) for row in data["metadata_json"].tolist()]
        X, y = data["X"], data["y"]
        require(audit["filter_bank_sha256"] == file_hash(filter_bank_json) and (audit["data_module_sha256"] == file_hash(__file__) or legacy_compatible(audit)),
                "Cached preprocessing identity differs from current frozen implementation")
        dataset = _dataset_key(audit["dataset"])
        expected_n, expected_counts = population(dataset, audit["provider_subject"])
        require(audit["units"] == "dimensionless" and audit["normalization"] == NORMALIZATION and
                len(rows) == expected_n and
                Counter(row["y"] for row in rows) == expected_counts,
                "Cached trial population/normalization contract changed")
        require(X.dtype == np.float32 and X.shape == (len(rows), 3, 18, 320) and np.isfinite(X).all(), "Invalid cached EEG array")
        require(y.dtype == np.int64 and y.shape == (len(rows),) and y.tolist() == [row["y"] for row in rows], "Cached labels differ")
        require(audit["X_sha256"] == array_hash(X) and audit["y_sha256"] == array_hash(y) and
                audit["metadata_sha256"] == object_hash(rows), "Cached array/metadata hash mismatch")
        require(len({row["trial_id"] for row in rows}) == len(rows), "Duplicate cached physical trials")
        for key in ("dataset", "subject", "session", "run", "trial_id"):
            require(data[key].tolist() == [row[key] for row in rows], f"Cached metadata column differs: {key}")
    return audit


def prepare_dataset(dataset: str, source_root: str | Path, output_dir: str | Path,
                    filter_bank_json: str | Path = DEFAULT_FILTER_BANK,
                    manifest_path: str | Path | None = None, subjects: list[int] | None = None,
                    yang_unit_policy: str | None = None) -> list[dict]:
    dataset = _dataset_key(dataset)
    people = roster(dataset) if subjects is None else [_subject_number(dataset, s) for s in subjects]
    require(people and len(people) == len(set(people)) and set(people).issubset(roster(dataset)), "Unique retained dataset subjects required")
    result = []
    for person in people:
        output = Path(output_dir) / f"sub-{person:03d}.npz"
        result.append(build_subject_npz(dataset, person, source_root, output, filter_bank_json,
                                        manifest_path=manifest_path, yang_unit_policy=yang_unit_policy))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=tuple(DATASET_NAMES))
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--subject", action="append", type=int)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--filter-bank", type=Path, default=DEFAULT_FILTER_BANK)
    parser.add_argument("--yang-unit-policy", choices=[YANG_UNIT_CONVENTION])
    args = parser.parse_args()
    for receipt in prepare_dataset(args.dataset, args.source_root, args.output_dir, args.filter_bank,
                                    args.manifest, args.subject, args.yang_unit_policy):
        print(json.dumps({"subject": receipt["subject"], "trials": receipt["n_trials"],
                          "shape": receipt["shape"], "npz": receipt["npz_path"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
