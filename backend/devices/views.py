from django.db.models.deletion import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import APIException
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet

from devices.models import DeviceType, SignalDefinition, TestDefinition
from devices.permissions import DefinitionPermissions
from devices.serializers import (
    DeviceTypeSerializer,
    SignalDefinitionSerializer,
    TestDefinitionSerializer,
)


class DefinitionPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class DefinitionInUse(APIException):
    status_code = 409
    default_detail = "Remove dependent definitions before deleting this item."
    default_code = "definition_in_use"


class DefinitionViewSet(ModelViewSet):
    permission_classes = [DefinitionPermissions]
    pagination_class = DefinitionPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["name"]

    def perform_destroy(self, instance) -> None:
        try:
            instance.delete()
        except ProtectedError as error:
            raise DefinitionInUse() from error


class DeviceTypeViewSet(DefinitionViewSet):
    queryset = DeviceType.objects.all()
    serializer_class = DeviceTypeSerializer


class TestDefinitionViewSet(DefinitionViewSet):
    queryset = TestDefinition.objects.select_related("device_type")
    serializer_class = TestDefinitionSerializer
    filterset_fields = ["device_type"]
    search_fields = ["name", "device_type__name"]


class SignalDefinitionViewSet(DefinitionViewSet):
    queryset = SignalDefinition.objects.select_related("test__device_type")
    serializer_class = SignalDefinitionSerializer
    filterset_fields = ["test"]
    search_fields = ["name", "test__name", "test__device_type__name"]
