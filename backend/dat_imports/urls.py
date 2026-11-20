from django.urls import path

from dat_imports.views import DatImportView, DatPreviewView


urlpatterns = [
    path("preview/", DatPreviewView.as_view(), name="dat-preview"),
    path("import/", DatImportView.as_view(), name="dat-import"),
]
