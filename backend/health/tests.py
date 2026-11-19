from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "backend"])
class HealthTests(SimpleTestCase):
    def test_health_returns_json_without_database_access(self) -> None:
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Content-Type"], "application/json")

    def test_health_accepts_backend_proxy_host(self) -> None:
        response = self.client.get("/health", HTTP_HOST="backend:8000")

        self.assertEqual(response.status_code, 200)

    def test_post_is_not_allowed(self) -> None:
        response = self.client.post("/health")

        self.assertEqual(response.status_code, 405)

    def test_unknown_path_returns_not_found(self) -> None:
        response = self.client.get("/unknown")

        self.assertEqual(response.status_code, 404)

    def test_untrusted_host_is_rejected(self) -> None:
        response = self.client.get("/health", HTTP_HOST="untrusted.example")

        self.assertEqual(response.status_code, 400)
