from django.db.models.deletion import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import APIException
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet

from devices.models import DeviceType, SignalDefinition, TestDefinition, TestRun
from devices.permissions import ModelPermissions
from devices.serializers import (
    DeviceTypeSerializer,
    SignalDefinitionSerializer,
    TestDefinitionSerializer,
    TestRunSerializer,
    TestRunListSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class RecordInUse(APIException):
    status_code = 409
    default_detail = "Remove dependent records before deleting this item."
    default_code = "definition_in_use"


class ProtectedModelViewSet(ModelViewSet):
    permission_classes = [ModelPermissions]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["name"]

    def perform_destroy(self, instance) -> None:
        try:
            instance.delete()
        except ProtectedError as error:
            raise RecordInUse() from error


class DeviceTypeViewSet(ProtectedModelViewSet):
    queryset = DeviceType.objects.all()
    serializer_class = DeviceTypeSerializer


class TestDefinitionViewSet(ProtectedModelViewSet):
    queryset = TestDefinition.objects.select_related("device_type")
    serializer_class = TestDefinitionSerializer
    filterset_fields = ["device_type"]
    search_fields = ["name", "device_type__name"]


class SignalDefinitionViewSet(ProtectedModelViewSet):
    queryset = SignalDefinition.objects.select_related("test__device_type")
    serializer_class = SignalDefinitionSerializer
    filterset_fields = ["test"]
    search_fields = ["name", "test__name", "test__device_type__name"]


class TestRunViewSet(ProtectedModelViewSet):
    queryset = TestRun.objects.select_related("test", "device_type", "recorded_by")
    serializer_class = TestRunSerializer
    filterset_fields = ["test", "device_type"]
    search_fields = ["device_serial_number", "test__name", "device_type__name"]

    def get_serializer_class(self):
        return TestRunListSerializer if self.action == "list" else TestRunSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.defer("flat_result_data") if self.action == "list" else queryset

    def perform_create(self, serializer) -> None:
        serializer.save(recorded_by=self.request.user)
