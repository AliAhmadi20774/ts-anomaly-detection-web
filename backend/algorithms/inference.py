"""Analyze stored test signals with a registered reconstruction model."""

from dataclasses import dataclass
from itertools import islice
import math
from uuid import UUID

from django.core.exceptions import ValidationError

from algorithms.loading import load_model
from algorithms.models import ModelVersion
from algorithms.preprocessing import iter_preprocessed_windows
from algorithms.runtimes.contracts import ReconstructionRuntime
from algorithms.runtimes.torch_inference import validate_reconstruction_repeats
from devices.models import SignalTrace, TestRun


@dataclass(frozen=True, slots=True)
class WindowScore:
    """One window's MSE and half-open bounds in the original test signal."""

    start_sample: int
    end_sample: int
    start_time_s: float
    end_time_s: float
    score: float


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """CPU-native results and the execution options needed to interpret them."""

    test_run_id: UUID
    model_version_id: UUID
    features: tuple[str, ...]
    source_sample_rate_hz: float
    stride: int
    batch_size: int
    reconstruction_repeats: int
    windows: tuple[WindowScore, ...]


def _read_signals(test_run: TestRun, features: list[str]) -> list[list[float]]:
    """Select measured signals by exact name and preserve the model's column order."""
    traces = SignalTrace.objects.filter(
        test_run=test_run, signal_definition__name__in=features,
    ).values_list("signal_definition__name", "signal_definition__test_id", "samples")
    signals = {}
    for name, definition_test_id, samples in traces:
        if definition_test_id != test_run.test_id or name in signals:
            raise ValueError("Signal traces must belong to this test definition and have unique names.")
        signals[name] = samples
    missing = [name for name in features if name not in signals]
    if missing:
        raise ValueError(f"Missing model input signal(s): {', '.join(missing)}.")
    columns = [signals[name] for name in features]
    if not columns[0] or any(len(column) != len(columns[0]) for column in columns):
        raise ValueError("Model input signals must be non-empty and have equal sample counts.")
    return columns


def analyze_test(
    test_run_id, model_version_id, *, stride: int, batch_size: int = 100,
    reconstruction_repeats: int = 10, start_sample: int = 0, end_sample: int | None = None,
) -> AnalysisResult:
    """Read a test, preprocess its input signals and score complete windows.

    Signal names must match input_spec.features exactly; there are no implicit
    aliases, substitutions, normalization fitting or zero padding. Signals use
    the sample rate snapshotted on TestRun, not the current test definition.

    start_sample/end_sample select a half-open range in ORIGINAL samples. Call
    separately for distinct sections; windows never cross a supplied boundary.
    stride counts processed samples, including when resampling is configured.
    Returned seconds are relative to the beginning of the original test signal.

    The model is loaded once. Each batch's inputs follow its device and dtype;
    only final scalar scores are copied to CPU. Batch size bounds inference
    tensor memory, not the stored source arrays or returned score collection.
    LSTM state initialization is stochastic: batch size and repeats can affect
    scores. This service does not set global random seeds or thread settings.

    Missing database IDs raise DoesNotExist. Invalid inputs/settings raise
    ValidationError. No records, source signals or model files are changed.
    This service returns scores only; thresholds and result persistence belong
    to later steps. It is permanent backend code, not a migration script.
    """
    try:
        for name, value in (("stride", stride), ("batch_size", batch_size)):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        validate_reconstruction_repeats(reconstruction_repeats)
        if type(start_sample) is not int or start_sample < 0:
            raise ValueError("start_sample must be a non-negative integer.")
        if end_sample is not None and (type(end_sample) is not int or end_sample <= start_sample):
            raise ValueError("end_sample must be an integer greater than start_sample.")

        test_run = TestRun.objects.get(pk=test_run_id)
        version = ModelVersion.objects.select_related("algorithm", "weights").get(pk=model_version_id)
        version.full_clean()
        features = version.input_spec["features"]
        columns = _read_signals(test_run, features)
        source_length = len(columns[0])
        end_sample = source_length if end_sample is None else end_sample
        if not start_sample < end_sample <= source_length:
            raise ValueError("The selected sample range must be inside the measured signals.")
        samples = zip(*(column[start_sample:end_sample] for column in columns), strict=True)
        windows = iter_preprocessed_windows(
            samples, preprocessing=version.preprocessing, input_spec=version.input_spec,
            stride=stride, offset=start_sample, source_sample_rate_hz=test_run.sample_rate_hz,
        )
        batch = list(islice(windows, batch_size))
        if not batch:
            raise ValueError("The selected sample range does not contain a complete model window.")

        runtime = load_model(version)
        if not isinstance(runtime, ReconstructionRuntime):
            raise ValueError("This model runtime does not support reconstruction-based analysis.")
        results = []
        while batch:
            prediction = runtime.predict(
                [window.values for window in batch], reconstruction_repeats=reconstruction_repeats,
            )
            if prediction.reconstruction_repeats != reconstruction_repeats:
                raise ValueError("The runtime did not use the requested reconstruction repeat count.")
            scores = prediction.scores.detach().cpu().tolist()
            del prediction  # Release the GPU reconstruction before the next batch.
            if not isinstance(scores, list) or len(scores) != len(batch) or any(
                type(score) not in (int, float) or not math.isfinite(score) or score < 0 for score in scores
            ):
                raise ValueError("The model must return one finite, non-negative score per window.")
            for window, score in zip(batch, scores, strict=True):
                results.append(WindowScore(
                    start_sample=window.start, end_sample=window.end,
                    start_time_s=window.start / test_run.sample_rate_hz,
                    end_time_s=window.end / test_run.sample_rate_hz, score=float(score),
                ))
            batch = list(islice(windows, batch_size))
        return AnalysisResult(
            test_run_id=test_run.pk, model_version_id=version.pk, features=tuple(features),
            source_sample_rate_hz=test_run.sample_rate_hz, stride=stride, batch_size=batch_size,
            reconstruction_repeats=reconstruction_repeats, windows=tuple(results),
        )
    except ValueError as error:
        raise ValidationError(str(error)) from error
