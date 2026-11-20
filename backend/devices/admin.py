from django.contrib import admin

from devices.models import DeviceRun, DeviceType, MeasurementBatch, SignalDefinition, SignalTrace, TestDefinition, TestRun


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "id")
    search_fields = ("name",)
    list_per_page = 50


@admin.register(TestDefinition)
class TestDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "device_type", "sample_rate_hz")
    list_filter = ("device_type",)
    search_fields = ("name", "device_type__name")
    autocomplete_fields = ("device_type",)
    list_select_related = ("device_type",)
    list_per_page = 50


@admin.register(SignalDefinition)
class SignalDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "test")
    list_filter = ("test__device_type",)
    search_fields = ("name", "test__name", "test__device_type__name")
    autocomplete_fields = ("test",)
    list_select_related = ("test__device_type",)
    list_per_page = 50


@admin.register(MeasurementBatch)
class MeasurementBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "recorded_by")
    readonly_fields = ("id", "created_at", "recorded_by")
    list_select_related = ("recorded_by",)

    def has_add_permission(self, request):
        return False


@admin.register(DeviceRun)
class DeviceRunAdmin(admin.ModelAdmin):
    list_display = ("serial_number", "device_type", "batch")
    search_fields = ("serial_number", "device_type__name")
    list_select_related = ("device_type", "batch")
    readonly_fields = ("batch", "device_type", "serial_number")

    def has_add_permission(self, request):
        return False


@admin.register(TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = ("device_serial_number", "test", "executed_at", "recorded_by")
    list_filter = ("device_type",)
    search_fields = ("device_serial_number", "test__name", "recorded_by__username")
    autocomplete_fields = ("test",)
    readonly_fields = ("device_run", "device_type", "sample_rate_hz", "recorded_by", "created_at")
    list_select_related = ("test", "device_type", "recorded_by", "device_run__batch")
    list_per_page = 50

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("test", "device_serial_number") if obj else ())

    def save_model(self, request, obj, form, change) -> None:
        if not change:
            obj.recorded_by = request.user
            batch = MeasurementBatch.objects.create(recorded_by=request.user)
            obj.device_run = DeviceRun.objects.create(
                batch=batch, device_type=obj.test.device_type, serial_number=obj.device_serial_number,
            )

        super().save_model(request, obj, form, change)


@admin.register(SignalTrace)
class SignalTraceAdmin(admin.ModelAdmin):
    list_display = ("test_run", "signal_definition", "sample_count")
    search_fields = ("test_run__device_serial_number", "signal_definition__name")
    list_select_related = ("test_run", "signal_definition")

    @admin.display(description="Samples")
    def sample_count(self, obj: SignalTrace) -> int:
        return len(obj.samples)
