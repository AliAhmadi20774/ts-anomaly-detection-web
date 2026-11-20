from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from dat_imports.permissions import CanPreviewDat
from dat_imports.importer import DatImportService
from dat_imports.preview import DatPreviewService
from dat_imports.serializers import DatPreviewSerializer


@method_decorator(never_cache, name="dispatch")
class DatPreviewView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [CanPreviewDat]

    def post(self, request) -> Response:
        serializer = DatPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        preview = DatPreviewService().preview(data["files"], data["file_format"], data["device_type"])
        return Response({**preview, "previewed_by_code": request.user.username})


@method_decorator(never_cache, name="dispatch")
class DatImportView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [CanPreviewDat]

    def post(self, request) -> Response:
        serializer = DatPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["file_format"] == "legacy":
            return Response({"file_format": ["Import currently supports current-format DAT files only."]}, status=400)
        return Response(DatImportService().import_files(data["files"], request.user, data["device_type"]))
