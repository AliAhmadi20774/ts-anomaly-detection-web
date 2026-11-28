"""Analyze stored test signals with a registered reconstruction model."""

from dataclasses import dataclass
from itertools import islice
import math
from typing import Literal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction

from algorithms.loading import load_model
from algorithms.models import SectionModelConfig
from algorithms.preprocessing import iter_preprocessed_windows
from algorithms.runtimes.contracts import ReconstructionRuntime
from devices.models import SignalTrace, TestRun


@dataclass(frozen=True, slots=True)
class WindowScore:
    """One window's MSE, decision and half-open original-sample bounds."""

    start_sample: int
    end_sample: int
    start_time_s: float
    end_time_s: float
    score: float
    status: Literal["normal", "anomaly"]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """CPU-native results and the execution options needed to interpret them."""

    test_run_id: UUID
    config_id: UUID
    section_id: UUID
    model_version_id: UUID
    features: tuple[str, ...]
    signal_ids: tuple[UUID, ...]
    source_sample_rate_hz: float
    stride: int
    batch_size: int
    inference_params: dict
    threshold: float
    windows: tuple[WindowScore, ...]


def _read_signals(test_run: TestRun, signal_ids: tuple[UUID, ...]) -> list[list[float]]:
    """Read explicitly bound signals in model feature order, independently of names."""
    traces = SignalTrace.objects.filter(
        test_run=test_run, signal_definition_id__in=signal_ids,
    ).values_list("signal_definition_id", "samples")
    signals = dict(traces)
    missing = [str(signal_id) for signal_id in signal_ids if signal_id not in signals]
    if missing:
        raise ValueError(f"Missing measured signal(s): {', '.join(missing)}.")
    columns = [signals[signal_id] for signal_id in signal_ids]
    if not columns[0] or any(len(column) != len(columns[0]) for column in columns):
        raise ValueError("Model input signals must be non-empty and have equal sample counts.")
    return columns


def _read_configuration(test_run_id, config_id):
    """Snapshot and validate metadata before loading weights or allocating GPU data.

    Under autocommit, locks last only for these reads. Locking the configuration
    also prevents new input bindings during the snapshot (through its FK).
    Call outside caller-owned transactions to release locks before inference.
    """
    with transaction.atomic():
        test_run = TestRun.objects.get(pk=test_run_id)
        config = SectionModelConfig.objects.select_related(
            "section", "model_version__algorithm", "model_version__weights",
        ).select_for_update(of=("self", "section", "model_version", "model_version__algorithm")).get(pk=config_id)
        config.section.full_clean()
        config.model_version.full_clean()
        config.full_clean()
        if test_run.test_id != config.section.test_id:
            raise ValueError("The test run must belong to the section's test definition.")

        bindings = list(config.inputs.select_related("signal").select_for_update(of=("self", "signal")))
        features = config.model_version.input_spec["features"]
        by_feature = {}
        for binding in bindings:
            binding.config = config
            binding.full_clean()
            by_feature[binding.feature_name] = binding.signal_id
        if set(by_feature) != set(features):
            raise ValueError("Every model feature must have exactly one explicit signal binding.")
        signal_ids = tuple(by_feature[feature] for feature in features)
        columns = _read_signals(test_run, signal_ids)
    return test_run, config, signal_ids, columns


def analyze_test(test_run_id, config_id) -> AnalysisResult:
    """Analyze one stored section configuration against a matching test run.

    The database supplies section bounds, signal bindings, model, threshold,
    stride, batch size and algorithm-specific inference settings. There are no
    fallback thresholds or inferred input mappings. ModelVersion supplies the
    trained preprocessing and feature order. TestRun supplies the recorded rate.

    Bounds refer to original samples, while stride counts processed samples.
    One joint MSE per window is anomalous only when strictly above threshold.
    Results are returned without persistence; source data is never modified.
    The model loads once and batches follow its device and dtype automatically.
    Missing IDs raise DoesNotExist; invalid configurations raise ValidationError.
    """
    try:
        test_run, config, signal_ids, columns = _read_configuration(test_run_id, config_id)
        version = config.model_version
        features = version.input_spec["features"]
        start_sample, end_sample = config.section.start_sample, config.section.end_sample
        stride, batch_size = config.stride, config.batch_size
        threshold = config.threshold
        source_length = len(columns[0])
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
                [window.values for window in batch], **config.inference_params,
            )
            if "reconstruction_repeats" in config.inference_params and (
                prediction.reconstruction_repeats != config.inference_params["reconstruction_repeats"]
            ):
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
                    status="anomaly" if score > threshold else "normal",
                ))
            batch = list(islice(windows, batch_size))
        return AnalysisResult(
            test_run_id=test_run.pk, config_id=config.pk, section_id=config.section_id,
            model_version_id=version.pk, features=tuple(features), signal_ids=signal_ids,
            source_sample_rate_hz=test_run.sample_rate_hz, stride=stride, batch_size=batch_size,
            inference_params=dict(config.inference_params), threshold=threshold, windows=tuple(results),
        )
    except ValueError as error:
        raise ValidationError(str(error)) from error
