from uuid import uuid4

from django.core.validators import RegexValidator
from django.db import models


class Algorithm(models.Model):
    """Identify an algorithm family independently of its trained model versions."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    key = models.CharField(
        max_length=64,
        unique=True,
        validators=[RegexValidator(
            r"\A[a-z][a-z0-9_]*\Z",
            "Use lowercase letters, digits and underscores, starting with a letter.",
        )],
    )
    name = models.CharField(
        max_length=160,
        validators=[RegexValidator(r"\S", "Name must contain a non-whitespace character.")],
    )

    class Meta:
        db_table = "algorithms"
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(key__regex=r"\A[a-z][a-z0-9_]*\Z"),
                name="algorithms_key_format",
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=r"\S"),
                name="algorithms_name_not_blank",
            ),
        ]

    def __str__(self) -> str:
        return self.name
