from django.contrib import admin

from devices.models import DeviceType, SignalDefinition, TestDefinition


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
