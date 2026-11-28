from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from algorithms.loading import load_model_version
from algorithms.models import ModelVersion


class Command(BaseCommand):
    # Temporary diagnostic until the main inference workflow is available.
    help = "Check registered weights using the selected algorithm's loader without running inference."

    def add_arguments(self, parser):
        parser.add_argument("model_version_id", type=UUID)

    def handle(self, *args, **options):
        try:
            model = load_model_version(options["model_version_id"])
        except ModelVersion.DoesNotExist as error:
            raise CommandError("Model version does not exist.") from error
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        self.stdout.write(self.style.SUCCESS(
            f"Model weights loaded for {model.algorithm_key}: {len(model.features)} feature(s)."
        ))
