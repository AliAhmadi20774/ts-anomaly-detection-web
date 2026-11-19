from django.urls import path

from dat_imports.views import DatPreviewView


urlpatterns = [path("preview/", DatPreviewView.as_view(), name="dat-preview")]
