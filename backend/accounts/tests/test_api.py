from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase


class SessionApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = get_user_model().objects.create_superuser(
            username="001", password="test-session-password"
        )
        cls.inactive_user = get_user_model().objects.create_user(
            username="002", password="test-session-password", is_active=False
        )

    def setUp(self) -> None:
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf_token(self) -> str:
        response = self.client.get(reverse("auth-csrf"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrfToken", response.data)
        return self.client.cookies["csrftoken"].value

    def sign_in(self):
        return self.client.post(
            reverse("auth-login"),
            {"username": "001", "password": "test-session-password"},
            format="json", HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

    def test_login_persists_session_and_returns_permissions_without_email(self) -> None:
        response = self.sign_in()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "001")
        self.assertIn("devices.view_devicetype", response.data["permissions"])
        self.assertNotIn("email", response.data)
        self.assertNotIn("password", response.data)
        self.assertEqual(self.client.get(reverse("auth-me")).data["username"], "001")
        self.assertEqual(self.client.get(reverse("device-type-list")).status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_login_requires_csrf_even_when_anonymous(self) -> None:
        response = self.client.post(
            reverse("auth-login"),
            {"username": "001", "password": "test-session-password"}, format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_or_inactive_credentials_are_rejected(self) -> None:
        for username, password in (
            ("001", "incorrect"), ("missing", "incorrect"),
            ("002", "test-session-password"),
        ):
            with self.subTest(username=username):
                response = self.client.post(
                    reverse("auth-login"),
                    {"username": username, "password": password},
                    format="json", HTTP_X_CSRFTOKEN=self.csrf_token(),
                )
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 403)

    def test_logout_requires_csrf_and_invalidates_session(self) -> None:
        self.assertEqual(self.sign_in().status_code, 200)
        self.assertEqual(
            self.client.post(reverse("auth-logout"), {}, format="json").status_code, 403
        )
        response = self.client.post(
            reverse("auth-logout"), {}, format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 403)
        self.assertEqual(self.client.get(reverse("device-type-list")).status_code, 403)

    def test_forwarded_frontend_host_is_allowed_but_untrusted_origin_is_rejected(self) -> None:
        token = self.csrf_token()
        response = self.client.post(
            reverse("auth-login"),
            {"username": "001", "password": "test-session-password"}, format="json",
            HTTP_X_CSRFTOKEN=token, HTTP_HOST="localhost:3000",
            HTTP_ORIGIN="http://untrusted.example",
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse("auth-login"),
            {"username": "001", "password": "test-session-password"}, format="json",
            HTTP_X_CSRFTOKEN=token, HTTP_HOST="localhost:3000",
            HTTP_ORIGIN="http://localhost:3000",
        )
        self.assertEqual(response.status_code, 200)
