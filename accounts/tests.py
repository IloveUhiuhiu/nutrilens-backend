from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .serializers import RegisterSerializer
from .services import DEFAULT_AVATAR_URLS


class RegisterSerializerTests(SimpleTestCase):
    def test_create_assigns_random_default_avatar_when_avatar_is_missing(self):
        user = SimpleNamespace(
            id="user_12345678",
            email="test@example.com",
            save=lambda **kwargs: None,
            refresh_tdee=lambda current_weight: 0,
        )
        validated_data = {
            "email": user.email,
            "password": "StrongPass123",
            "full_name": "Test User",
            "gender": "M",
            "height": 170,
            "weight": 65,
        }

        with (
            patch("accounts.serializers.User.objects.create_user", return_value=user) as create_user,
            patch("accounts.serializers.WeightHistory.objects.create"),
            patch("accounts.serializers.get_random_default_avatar_url", return_value=DEFAULT_AVATAR_URLS[0]),
        ):
            created_user = RegisterSerializer().create(validated_data)

        self.assertEqual(created_user, user)
        self.assertEqual(create_user.call_args.kwargs["avatar_url"], DEFAULT_AVATAR_URLS[0])
