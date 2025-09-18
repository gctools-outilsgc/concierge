from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.contrib import auth
from django.core import signing
from django.test.client import RequestFactory
from django.http import HttpRequest
from unittest import mock

from core.models import User


class UserTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            name="John",
            email="john@user.com",
            password="GkCyKt6iWJVi"
        )
        self.superuser = User.objects.create_superuser(
            name="John",
            email="john@superuser.com",
            password="LZwHZucJj9JD"
        )

        self.factory = RequestFactory()

    def test_generated_username(self):
        """Make sure a correct unique username is generated for each user"""
        self.assertEqual(self.user.username, "john")
        self.assertEqual(self.superuser.username, "john-1")

    def test_normal_user_is_inactive_when_created(self):
        """Make sure a (normal) user is in inactive state when being created
        """
        self.assertIs(self.user.is_active, False)

    def test_superuser_is_active_when_created(self):
        """ Make sure a superuser is in active state when being created """
        self.assertIs(self.superuser.is_active, True)

    def test_login_with_email(self):
        """ Make sure a user can login with email and password """
        invalid_login = auth.authenticate(
            request=HttpRequest(),
            username="john@superuser.com",
            password="asdf"
        )
        valid_login = auth.authenticate(
            request=HttpRequest(),
            username="john@superuser.com",
            password="LZwHZucJj9JD"
        )
        self.assertEqual(invalid_login, None)
        self.assertEqual(valid_login, self.superuser)

    def test_account_activation(self):
        """ Test an account can be activated and login by using the activation
        token """
        request = self.factory.get("/")
        request.user = self.user

        middleware = SessionMiddleware()
        middleware.process_request(request)

        activation_token = signing.dumps(obj=self.user.email)
        with mock.patch('core.models.service_mesh_message', return_value=None):
            self.user.activate_user(activation_token)

        self.user.refresh_from_db()

        self.assertIs(self.user.is_active, True)
        self.assertEqual(request.user, self.user)
