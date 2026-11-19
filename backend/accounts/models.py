from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models

from accounts.managers import UserManager


class User(AbstractUser):
    """Identify a user by personnel code, preserving any leading zeros."""

    username = models.CharField(
        "personnel code",
        max_length=150,
        unique=True,
        validators=[UnicodeUsernameValidator()],
    )
    email = None
    REQUIRED_FIELDS = []

    objects = UserManager()
