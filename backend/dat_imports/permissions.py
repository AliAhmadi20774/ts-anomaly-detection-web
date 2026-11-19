from rest_framework.permissions import BasePermission


class CanPreviewDat(BasePermission):
    def has_permission(self, request, view) -> bool:
        permissions = ("devices.add_testrun", "devices.view_devicetype", "devices.view_testdefinition", "devices.view_signaldefinition")
        return bool(request.user and request.user.is_authenticated and request.user.has_perms(permissions))
