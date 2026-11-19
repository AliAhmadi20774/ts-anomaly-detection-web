from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Create accounts using a personnel code without an email address."""

    use_in_migrations = True

    def create_user(self, username: str, password: str | None = None, **extra_fields):
        if not username:
            raise ValueError("A personnel code is required.")
        user = self.model(
            username=self.model.normalize_username(username), **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self.create_user(username, password, **extra_fields)
