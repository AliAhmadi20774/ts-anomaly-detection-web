from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import APIException
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from devices.models import DeviceRun, DeviceType, MeasurementBatch, SignalDefinition, SignalTrace, TestDefinition, TestRun
from devices.permissions import ModelPermissions
from devices.serializers import (
    DeviceTypeSerializer,
    SignalDefinitionSerializer,
    MeasurementBatchSerializer,
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


class MeasurementBatchViewSet(ReadOnlyModelViewSet):
    queryset = MeasurementBatch.objects.select_related("recorded_by").prefetch_related(
        "devices__device_type", "devices__test_runs__test",
    )
    serializer_class = MeasurementBatchSerializer
    permission_classes = [ModelPermissions]
    pagination_class = StandardPagination


class TestRunViewSet(ProtectedModelViewSet):
    queryset = TestRun.objects.select_related("test", "device_type", "recorded_by", "device_run__batch")
    serializer_class = TestRunSerializer
    filterset_fields = ["test", "device_type"]
    search_fields = ["device_serial_number", "test__name", "device_type__name"]

    def get_serializer_class(self):
        return TestRunListSerializer if self.action == "list" else TestRunSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.defer("flat_result_data") if self.action == "list" else queryset

    def perform_create(self, serializer) -> None:
        with transaction.atomic():
            definition = serializer.validated_data["test"]
            batch = MeasurementBatch.objects.create(recorded_by=self.request.user)
            device_run = DeviceRun.objects.create(
                batch=batch,
                device_type=definition.device_type,
                serial_number=serializer.validated_data["device_serial_number"],
            )
            serializer.save(recorded_by=self.request.user, device_run=device_run)

    def perform_destroy(self, instance) -> None:
        with transaction.atomic():
            device_run = instance.device_run
            batch = device_run.batch
            super().perform_destroy(instance)
            if not device_run.test_runs.exists():
                device_run.delete()
            if not batch.devices.exists():
                batch.delete()

    @action(detail=True, methods=["get"])
    def signals(self, request, pk=None) -> Response:
        run = self.get_object()
        traces = SignalTrace.objects.filter(test_run=run).select_related("signal_definition")
        return Response([
            {"id": str(trace.pk), "name": trace.signal_definition.name, "sample_count": len(trace.samples)}
            for trace in traces
        ])

    @action(detail=True, methods=["get"], url_path=r"signals/(?P<signal_id>[^/.]+)")
    def signal_samples(self, request, pk=None, signal_id=None) -> Response:
        run = self.get_object()
        trace = get_object_or_404(
            SignalTrace.objects.select_related("signal_definition"), pk=signal_id, test_run=run,
        )
        return Response({"id": str(trace.pk), "name": trace.signal_definition.name, "samples": trace.samples})
