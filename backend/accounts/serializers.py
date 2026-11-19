from rest_framework import serializers

from accounts.models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(label="Personnel code")
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class CurrentUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "name", "is_superuser", "permissions")

    def get_name(self, user: User) -> str:
        return user.get_full_name() or user.username

    def get_permissions(self, user: User) -> list[str]:
        return sorted(user.get_all_permissions())
