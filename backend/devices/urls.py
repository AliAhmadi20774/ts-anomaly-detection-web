from rest_framework.routers import DefaultRouter

from devices.views import (
    DeviceTypeViewSet,
    SignalDefinitionViewSet,
    TestDefinitionViewSet,
    TestRunViewSet,
)


router = DefaultRouter()
router.register("device-types", DeviceTypeViewSet, basename="device-type")
router.register("test-definitions", TestDefinitionViewSet, basename="test-definition")
router.register("signal-definitions", SignalDefinitionViewSet, basename="signal-definition")
router.register("test-runs", TestRunViewSet, basename="test-run")

urlpatterns = router.urls
