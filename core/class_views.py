from urllib.parse import urlparse

from django.urls import reverse_lazy
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.views import PasswordResetConfirmView, PasswordContextMixin
from two_factor.forms import BackupTokenForm
from two_factor.views.core import LoginView, BackupTokensView
from two_factor.views.profile import ProfileView
from user_sessions.views import (
    SessionListView,
    SessionDeleteOtherView,
    SessionDeleteView
)
from django_otp.plugins.otp_static.models import StaticToken

from .models import PleioPartnerSite, User
from .forms import PleioAuthenticationTokenForm, LabelledLoginForm
from axes.helpers import get_client_cache_keys, get_cache
from pleio_account import settings

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_decode
from django.http import HttpResponseRedirect
from django.views.generic.edit import FormView

UserModel = get_user_model()

class PleioLoginView(LoginView):

    template_name = 'login.html'

    form_list = (
        ('auth', LabelledLoginForm),
        ('token', PleioAuthenticationTokenForm),
        ('backup', BackupTokenForm),
    )

    def get_context_data(self, **kwargs):
        cache_hash_key = get_client_cache_keys(self.request)[1]
        attempt = get_cache().get(cache_hash_key)
        if not attempt:
            attempt = 0
        username = self.request.POST.get('auth-username', None)
        time = settings.AXES_COOLOFF_TIME
        attempts_left = (settings.AXES_FAILURE_LIMIT - attempt)
        kwargs= dict(kwargs, attempt=attempt, username=username, time=time, attempts_left=attempts_left)
        
        context = super().get_context_data(**kwargs)
        self.set_partner_site_info()
        context[self.redirect_field_name] = self.request.POST.get(
            self.redirect_field_name,
            self.request.GET.get(self.redirect_field_name, '')
        )
        return context

    def set_partner_site_info(self):
        try:
            http_referer = urlparse(self.request.META['HTTP_REFERER'])
        except Exception:
            # no referer: cookies have to be deleted in PartnerSiteMiddleware
            self.request.COOKIES['partner_site_url'] = None
            self.request.COOKIES['partner_site_name'] = None
            self.request.COOKIES['partner_site_logo_url'] = None
            return False

        try:
            clean_url = http_referer.scheme+"://"+http_referer.netloc+"/"
            if http_referer.netloc == self.request.META['HTTP_HOST']:
                # referer is this site: no action to be taken
                return False
            try:
                # search for matching partnersite data
                partnersite = PleioPartnerSite.objects.get(partner_site_url=clean_url)
                self.request.COOKIES['partner_site_url'] = partnersite.partner_site_url
                self.request.COOKIES['partner_site_name'] = partnersite.partner_site_name
                self.request.COOKIES['partner_site_logo_url'] = partnersite.partner_site_logo_url
            except Exception:
                try:
                    # no matching partnersite data found: default background image will be used
                    partnersite = PleioPartnerSite.objects.get(partner_site_url='http://localhost')
                    self.request.COOKIES['partner_site_url'] = clean_url
                    self.request.COOKIES['partner_site_name'] = http_referer.netloc
                    self.request.COOKIES['partner_site_logo_url'] = partnersite.partner_site_logo_url
                except Exception:
                    return False
        except Exception:
            return False

        return True

    def done(self, form_list, **kwargs):
        self.request.session.set_expiry(30 * 24 * 60 * 60)

        user = self.get_user()
        user.check_users_previous_logins(self.request)

        return super().done(form_list, **kwargs)


class PleioProfileView(ProfileView):
    """
    View used by users for managing two-factor configuration.

    This view shows whether two-factor has been configured for the user's
    account. If two-factor is enabled, it also lists the primary verification
    method and backup verification methods.
    """
    def dispatch(self, request, *args, **kwargs):
        handler = getattr(self, 'get', self.http_method_not_allowed)

        self.request = request
        self.args = args
        self.kwargs = kwargs

        return handler(request, *args, **kwargs)


class PleioSessionListView(SessionListView):
    """
    View for listing a user's own sessions.

    This view shows list of a user's currently active sessions. You can
    override the template by providing your own template at
    `user_sessions/session_list.html`.
    """
    def dispatch(self, request, *args, **kwargs):
        handler = getattr(self, 'get', self.http_method_not_allowed)

        self.request = request
        self.args = args
        self.kwargs = kwargs

        return handler(request, *args, **kwargs)


class PleioSessionDeleteView(SessionDeleteView):
    """
    View for deleting all user's sessions but the current.

    This view allows a user to delete all other active session. For example
    log out all sessions from a computer at the local library or a friend's
    place.
    """
    def get_success_url(self):
        return str(reverse_lazy('security_pages'))


class PleioSessionDeleteOtherView(SessionDeleteOtherView):
    """
    View for deleting all user's sessions but the current.

    This view allows a user to delete all other active session. For example
    log out all sessions from a computer at the local library or a friend's
    place.
    """
    def get_success_url(self):
        return str(reverse_lazy('security_pages'))


class PleioBackupTokensView(BackupTokensView):
    """
    View for listing and generating backup tokens.

    A user can generate a number of static backup tokens. When the user loses
    its phone, these backup tokens can be used for verification. These backup
    tokens should be stored in a safe location; either in a safe or underneath
    a pillow ;-).
    """

    def get_context_data(self, **kwargs):
        context = super(BackupTokensView, self).get_context_data(**kwargs)
        device = self.get_device()
        context['device'] = device
        context['tokens'] = device.token_set.all()

        return context

    def form_valid(self, form):
        """
        Delete existing backup codes and generate new ones.
        """
        device = self.get_device()
        device.token_set.all().delete()
        for n in range(self.number_of_tokens):
            device.token_set.create(token=StaticToken.random_token())

        return TemplateResponse(self.request, 'security_pages.html', {
                'form': form,
                'tokens': device.token_set.all()
            })

INTERNAL_RESET_URL_TOKEN = 'set_password-creer_un_mot_de_passe'
INTERNAL_RESET_SESSION_TOKEN = '_password_reset_token'

class i18nPasswordResetConfirmView(PasswordContextMixin, FormView):
    form_class = SetPasswordForm
    post_reset_login = False
    post_reset_login_backend = None
    success_url = reverse_lazy('password_reset_complete')
    template_name = 'registration/password_reset_confirm.html'
    title = _('Enter new password')
    token_generator = default_token_generator

    @method_decorator(sensitive_post_parameters())
    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        assert 'uidb64' in kwargs and 'token' in kwargs

        self.validlink = False
        self.user = self.get_user(kwargs['uidb64'])

        if self.user is not None:
            token = kwargs['token']
            if token == INTERNAL_RESET_URL_TOKEN:
                session_token = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN)
                if self.token_generator.check_token(self.user, session_token):
                    # If the token is valid, display the password reset form.
                    self.validlink = True
                    return super().dispatch(*args, **kwargs)
            else:
                if self.token_generator.check_token(self.user, token):
                    # Store the token in the session and redirect to the
                    # password reset form at a URL without the token. That
                    # avoids the possibility of leaking the token in the
                    # HTTP Referer header.
                    self.request.session[INTERNAL_RESET_SESSION_TOKEN] = token
                    redirect_url = self.request.path.replace(token, INTERNAL_RESET_URL_TOKEN)
                    return HttpResponseRedirect(redirect_url)

        # Display the "Password reset unsuccessful" page.
        return self.render(context=self.get_context_data())

    def get_user(self, uidb64):
        try:
            # urlsafe_base64_decode() decodes to bytestring
            uid = urlsafe_base64_decode(uidb64).decode()
            user = UserModel._default_manager.get(pk=uid)
        except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist, ValidationError):
            user = None
        return user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        del self.request.session[INTERNAL_RESET_SESSION_TOKEN]
        if self.post_reset_login:
            auth_login(self.request, user, self.post_reset_login_backend)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.validlink:
            context['validlink'] = True
        else:
            context.update({
                'form': None,
                'title': _('Password reset unsuccessful'),
                'validlink': False,
            })
        return context
