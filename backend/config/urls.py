from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("devices.urls")),
    path("api/dat/", include("dat_imports.urls")),
    path("", include("health.urls")),
]

# Serve admin assets locally while DEBUG is enabled.
urlpatterns += staticfiles_urlpatterns()
