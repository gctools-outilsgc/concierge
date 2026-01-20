from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.core import mail
from django.test.client import RequestFactory
from django.http import HttpResponse
from core.models import User, PreviousLogin


class PreviousLoginTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            name="John",
            email="john@user.com",
            password="GkCyKt6iWJVi",
            receives_newsletter=True
        )
        self.superuser = User.objects.create_superuser(
            name="John",
            email="john@superuser.com",
            password="LZwHZucJj9JD"
        )

        self.factory = RequestFactory()

    def test_send_email_suspicious_login(self):
        """ Test  sending an email after a suspicious login"""
        request = self.factory.get("/")
        request.user = self.user

        middleware = SessionMiddleware(lambda request : HttpResponse())
        middleware.process_request(request)

        # www.ziggo.nl an existing ip address
        request.session.ip = "8.247.18.183"
        request.session.user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Ubuntu Chromium/62.0.3202.75"
            " Chrome/62.0.3202.75 Safari/537.36"
        )

        device_id = "yj9zaceo1v6i6uw4hr0k2h8qs11zvjgd"
        request.COOKIES['device_id'] = device_id

        result = self.user.check_users_previous_logins(request)
        # No previous login found
        self.assertIs(result, False)
        # An email has been sent
        self.assertEqual(len(mail.outbox), 1)
        # Empty the test outbox
        mail.outbox = []

        result = self.user.check_users_previous_logins(request)
        # Confirmed previous login found
        self.assertIs(result, True)
        # No email has been sent
        self.assertEqual(len(mail.outbox), 0)
        # Empty the test outbox
        mail.outbox = []
