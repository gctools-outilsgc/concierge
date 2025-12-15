import requests
import json
from .models import User
from django.core.mail.backends.smtp import EmailBackend
from constance import config

from django.core.exceptions import PermissionDenied
from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_credentials, get_lockout_message
from axes.backends import AxesStandaloneBackend
from axes.exceptions import AxesBackendPermissionDenied, AxesBackendRequestParameterRequired

from .service_mesh import service_mesh_message

# Combine AxesModelBackend and ElggBackend into one backend
class ElggLockout(AxesStandaloneBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):

        if request is None:
            raise AxesBackendRequestParameterRequired(
                "AxesBackend requires a request as an argument to authenticate"
            )

        try:
            user = User.objects.get(email__iexact=username)
            if user.check_password(password):
                return
        except User.DoesNotExist:
            if config.ELGG_URL:
                elgg_urls =  config.ELGG_URL.splitlines()

                for url in elgg_urls:
                    # Verify username/password combination
                    valid_user_request = requests.post(
                        url + "/services/api/rest/json/",
                        data={
                            'method': 'pleio.verifyuser',
                            'user': username,
                            'password': password
                        }
                    )
                    valid_user_json = json.loads(valid_user_request.text)
                    valid_user_result = valid_user_json["result"] if 'result' in valid_user_json else []
                    valid_user = valid_user_result["valid"] if 'valid' in valid_user_result else False
                    name = valid_user_result["name"] if 'name' in valid_user_result else username
                    admin = valid_user_result["admin"] if 'admin' in valid_user_result else False

                    # If valid, create new user with Elgg attributes
                    if valid_user is True:
                        user = User.objects.create_user(
                            name=name,
                            email=username.lower(),
                            password=password,
                            accepted_terms=True,
                            receives_newsletter=True
                        )
                        user.is_active = True
                        user.is_admin = admin
                        user.save()
                        service_mesh_message('user.new', json.dumps({
                            'name': user.name,
                            'email': user.email,
                            'gcID': user.id,
                            'isAdmin': user.is_admin
                        }))
                        break

        credentials = get_credentials(username=username, password=password, **kwargs)

        if AxesProxyHandler.is_allowed(request, credentials):
            return

        error_msg = get_lockout_message()
        response_context = kwargs.get("response_context", {})
        response_context["error"] = error_msg

        if not settings.AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT:
            request.axes_locked_out = True

        raise AxesBackendPermissionDenied(
            "AxesBackend detected that the given user is locked out"
        )

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class ElggBackend:
    def authenticate(self, request, username=None, password=None):
        if not config.ELGG_URL:
            return

        # Check if user exists (case-insensitive)
        try:
            user = User.objects.get(email__iexact=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:

            elgg_urls =  config.ELGG_URL.splitlines()

            for url in elgg_urls:
                # Verify username/password combination
                valid_user_request = requests.post(
                    url + "/services/api/rest/json/",
                    data={
                        'method': 'pleio.verifyuser',
                        'user': username,
                        'password': password
                    }
                )
                valid_user_json = json.loads(valid_user_request.text)
                valid_user_result = valid_user_json["result"] if 'result' in valid_user_json else []
                valid_user = valid_user_result["valid"] if 'valid' in valid_user_result else False
                name = valid_user_result["name"] if 'name' in valid_user_result else username
                admin = valid_user_result["admin"] if 'admin' in valid_user_result else False

                # If valid, create new user with Elgg attributes
                if valid_user is True:
                    user = User.objects.create_user(
                        name=name,
                        email=username.lower(),
                        password=password,
                        accepted_terms=True,
                        receives_newsletter=True
                    )
                    user.is_active = True
                    user.is_admin = admin
                    user.save()
                    return user
                else:
                    return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class SiteConfigEmailBackend(EmailBackend):
    def __init__(self, host=None, port=None, username=None, password=None,
                 use_tls=None, fail_silently=None, use_ssl=None, timeout=None,
                 ssl_keyfile=None, ssl_certfile=None,
                 **kwargs):

        super(SiteConfigEmailBackend, self).__init__(
             host=host or config.EMAIL_HOST,
             port=port or config.EMAIL_PORT,
             username=username or config.EMAIL_USER,
             password=password or config.EMAIL_PASS,
             use_tls=use_tls or config.EMAIL_SECURITY == 'tls',
             use_ssl=use_ssl or config.EMAIL_SECURITY == 'ssl',
             fail_silently=fail_silently or config.EMAIL_FAIL_SILENTLY,
             timeout=timeout or config.EMAIL_TIMEOUT,
             ssl_keyfile=ssl_keyfile,
             ssl_certfile=ssl_certfile,
             **kwargs
        )

    #def send_messages(self, email_messages):
    #    return len(list(email_messages))

__all__ = ['SiteConfigEmailBackend']
