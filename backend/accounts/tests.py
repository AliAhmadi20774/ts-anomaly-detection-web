from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AccountTests(TestCase):
    def test_personnel_code_login_does_not_require_email(self) -> None:
        user = get_user_model().objects.create_user(
            username="001", password="test-account-password"
        )

        self.assertEqual(user.username, "001")
        self.assertTrue(self.client.login(username="001", password="test-account-password"))
        self.assertNotIn("email", {field.name for field in user._meta.fields})
        self.assertNotEqual(user.password, "test-account-password")

    def test_superuser_requires_administrative_flags(self) -> None:
        for flag in ("is_staff", "is_superuser"):
            with self.subTest(flag=flag):
                with self.assertRaises(ValueError):
                    get_user_model().objects.create_superuser(
                        username="1", password="test-account-password", **{flag: False}
                    )


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.administrator = get_user_model().objects.create_superuser(
            username="1", password="test-admin-password"
        )

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.client.get(reverse("admin:index"))

        self.assertRedirects(
            response, reverse("admin:login") + "?next=" + reverse("admin:index")
        )

    def test_nonstaff_user_cannot_access_admin(self) -> None:
        user = get_user_model().objects.create_user(
            username="002", password="test-account-password"
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)

    def test_user_form_has_personnel_code_and_no_email(self) -> None:
        self.client.force_login(self.administrator)

        response = self.client.get(reverse("admin:accounts_user_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Personnel code")
        self.assertNotContains(response, 'name="email"')

    def test_administrator_can_add_user_without_email(self) -> None:
        self.client.force_login(self.administrator)

        response = self.client.post(reverse("admin:accounts_user_add"), {
            "username": "003",
            "usable_password": "true",
            "password1": "Another-test-password-901!",
            "password2": "Another-test-password-901!",
            "_save": "Save",
        })

        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username="003")
        self.assertTrue(user.check_password("Another-test-password-901!"))

    def test_administrator_can_create_device_test_and_signal(self) -> None:
        from devices.models import DeviceType, SignalDefinition, TestDefinition

        self.client.force_login(self.administrator)
        response = self.client.post(reverse("admin:devices_devicetype_add"), {
            "name": "device1", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        device = DeviceType.objects.get(name="device1")

        response = self.client.post(reverse("admin:devices_testdefinition_add"), {
            "name": "test1", "device_type": str(device.id),
            "sample_rate_hz": "1000", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        test = TestDefinition.objects.get(name="test1")

        response = self.client.post(reverse("admin:devices_signaldefinition_add"), {
            "name": "signal1", "test": str(test.id), "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        signal = SignalDefinition.objects.get(name="signal1")
        self.assertEqual(signal.test.device_type, device)
        self.assertEqual(str(test), "device1 / test1")
