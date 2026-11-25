from pathlib import Path
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from algorithms.artifacts import register_weights
from algorithms.models import ModelVersion


class Command(BaseCommand):
    help = "Copy a weights file into private storage and attach it to an existing model version."

    def add_arguments(self, parser):
        parser.add_argument("model_version", type=UUID)
        parser.add_argument("file", type=Path)

    def handle(self, *args, **options):
        try:
            with options["file"].open("rb") as source:
                artifact = register_weights(options["model_version"], File(source))
        except ModelVersion.DoesNotExist as error:
            raise CommandError("Model version was not found.") from error
        except (OSError, ValidationError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(
            f"Registered {artifact.pk}: {artifact.file.name} ({artifact.size_bytes} bytes)"
        ))
