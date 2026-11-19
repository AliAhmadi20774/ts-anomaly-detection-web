from django.contrib import admin

from devices.models import DeviceType, SignalDefinition, TestDefinition, TestRun


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


@admin.register(TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = ("device_serial_number", "test", "executed_at", "recorded_by")
    list_filter = ("device_type",)
    search_fields = ("device_serial_number", "test__name", "recorded_by__username")
    autocomplete_fields = ("test",)
    readonly_fields = ("device_type", "sample_rate_hz", "recorded_by", "created_at")
    list_select_related = ("test", "device_type", "recorded_by")
    list_per_page = 50

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("test",) if obj else ())

    def save_model(self, request, obj, form, change) -> None:
        if not change:
            obj.recorded_by = request.user

        super().save_model(request, obj, form, change)
