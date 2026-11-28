"""One-time model transfer; ordinary loading never imports legacy code."""

import json
from pathlib import Path
import re

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from algorithms.artifacts import register_weights
from algorithms.models import Algorithm, ModelVersion
from algorithms.runtimes.registry import get_model_loader


def read_bundle(manifest_path: Path) -> list[tuple[dict, Path]]:
    """Validate every declared model and checkpoint before writing any records."""
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("Only model bundle schema_version 1 is supported.")
    if set(manifest) - {"schema_version", "models", "legacy"}:
        raise ValueError("Unknown bundle fields.")
    models = manifest.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("The bundle must contain a non-empty models list.")
    seen = set()
    plan = []
    for model in models:
        fields = {"algorithm", "version", "device_folder", "weights", "architecture_params", "input_spec", "preprocessing"}
        if not isinstance(model, dict) or set(model) != fields:
            raise ValueError("Each model must declare its identity, storage folder, weights and complete metadata.")
        if not isinstance(model["algorithm"], str) or not isinstance(model["device_folder"], str):
            raise ValueError("Algorithm and device folder must be strings.")
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", model["algorithm"]) is None:
            raise ValueError("Invalid algorithm key.")
        if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", model["device_folder"]) is None:
            raise ValueError("Invalid device folder.")
        if type(model["version"]) is not int or model["version"] < 1:
            raise ValueError("Version must be a positive integer.")
        identity = (model["algorithm"], model["version"])
        if identity in seen:
            raise ValueError("Duplicate algorithm/version in bundle.")
        seen.add(identity)
        relative = f"{model['device_folder']}/{model['algorithm']}/v{model['version']}/weights.bin"
        if model["weights"] != relative:
            raise ValueError("Weights must use <device-folder>/<algorithm>/v<version>/weights.bin.")
        source = (manifest_path.parent / relative).resolve()
        if not source.is_relative_to(manifest_path.parent) or not source.is_file():
            raise ValueError("Weights must be an existing file inside the bundle.")
        algorithm = Algorithm.objects.get(key=model["algorithm"])
        candidate = ModelVersion(
            algorithm=algorithm, version=model["version"],
            **{key: model[key] for key in ("architecture_params", "input_spec", "preprocessing")},
        )
        candidate.full_clean(validate_unique=False, validate_constraints=False)
        if candidate.preprocessing is None or sum(
            step["type"] == "window" for step in candidate.preprocessing["steps"]
        ) != 1:
            raise ValueError("Imported models require complete preprocessing with one window step.")
        # Reuse the actual loader's architecture and checkpoint validation. No
        # unrestricted pickle, legacy runtime or weights-only registration shortcut.
        with source.open("rb") as stream:
            runtime = get_model_loader(model["algorithm"])(
                stream, architecture_params=model["architecture_params"], input_spec=model["input_spec"],
            )
        del runtime
        plan.append((model, source))
    return plan


def check_existing(version: ModelVersion, model: dict, source: Path) -> None:
    """Allow completing missing preprocessing, but never replacing a recipe or file."""
    for key in ("architecture_params", "input_spec", "preprocessing"):
        existing = getattr(version, key)
        if key == "preprocessing" and existing is None:
            continue
        if existing != model[key]:
            raise ValueError(f"{version}: conflicting {key}; use a new version.")
    if version.weights_id:
        if version.weights.file.name != model["weights"] or version.weights.size_bytes != source.stat().st_size:
            raise ValueError(f"{version}: conflicting weight file or storage folder; use a new version.")
        with version.weights.file.open("rb") as stored, source.open("rb") as incoming:
            while chunk := incoming.read(64 * 1024):
                if stored.read(len(chunk)) != chunk:
                    raise ValueError(f"{version}: different weights; use a new version.")
            if stored.read(1):
                raise ValueError(f"{version}: different weights; use a new version.")


class Command(BaseCommand):
    help = "Preview or import a model bundle. Legacy execution policies stay in its JSON manifest."

    def add_arguments(self, parser):
        parser.add_argument("manifest", type=Path)
        parser.add_argument("--apply", action="store_true", help="Write validated model metadata and weights.")

    def handle(self, *args, **options):
        try:
            plan = read_bundle(options["manifest"])
            # Preflight all existing identities before the first filesystem write.
            for model, source in plan:
                version = ModelVersion.objects.filter(algorithm__key=model["algorithm"], version=model["version"]).first()
                if version:
                    check_existing(version, model, source)
                self.stdout.write(f"{model['algorithm']} v{model['version']}: {model['weights']}")
            if options["apply"]:
                with transaction.atomic():
                    for model, source in plan:
                        # Serialize imports for an algorithm, including new version
                        # allocation, and recheck metadata after acquiring the lock.
                        algorithm = Algorithm.objects.select_for_update().get(key=model["algorithm"])
                        version = ModelVersion.objects.filter(algorithm=algorithm, version=model["version"]).first()
                        if version:
                            check_existing(version, model, source)
                        else:
                            version = ModelVersion(
                                algorithm=algorithm, version=model["version"],
                                architecture_params=model["architecture_params"], input_spec=model["input_spec"],
                            )
                        version.preprocessing = model["preprocessing"]
                        version.full_clean()
                        version.save()
                        with source.open("rb") as stream:
                            register_weights(version.pk, File(stream), device_folder=model["device_folder"])
                self.stdout.write(self.style.SUCCESS(f"Imported {len(plan)} model(s). Repeating the import is safe."))
            else:
                self.stdout.write("Preview only: no records or stored files changed. Use --apply to import.")
            self.stdout.write(
                "Section bindings, thresholds and signal length policies remain in the source JSON; "
                "they are not active analysis settings or training provenance. Keep the bundle with your backup."
            )
        except (OSError, ValueError, TypeError, ValidationError, Algorithm.DoesNotExist) as error:
            raise CommandError(str(error)) from error
