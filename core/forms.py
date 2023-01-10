import json

import requests
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import password_validation
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.template import loader
from django.views.generic.edit import FormView
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.shortcuts import redirect
from two_factor.forms import AuthenticationTokenForm, TOTPDeviceForm
from emailvalidator.validator import is_email_valid
from constance import config
from axes.utils import reset
from oidc_provider.models import UserConsent

from .models import User
from .helpers import verify_captcha_response

from .service_mesh import service_mesh_message


class PasswordResetRequestForm(forms.Form):
    email = forms.CharField(label=("Email address"), max_length=254)


class ResetPasswordRequestView(FormView):
    template_name = "registration/password_reset.html"
    success_url = '/password_reset-reinitialiser_le_mot_de_passe/done-fait/'
    form_class = PasswordResetRequestForm

    @staticmethod
    def validate_email_address(email):
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            request.session['email'] = email

        if self.validate_email_address(email):
            found_user = User.objects.filter(email__iexact=email)
            if found_user.exists():

                for user in found_user:

                    if user.is_active is False:
                        return redirect('password_reset_not_active')

                    c = {
                        'domain': request.META['HTTP_HOST'],
                        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                        'user': user,
                        'token': default_token_generator.make_token(user),
                        'protocol': request.is_secure() and "https" or "http",
                        'app': config
                    }

                    subject_template_name = 'emails/reset_password_subject.txt'
                    email_template_name = 'emails/reset_password.txt'
                    html_email_template_name = 'emails/reset_password.html'
                    subject = loader.render_to_string(subject_template_name)
                    subject = ''.join(subject.splitlines())
                    email = loader.render_to_string(email_template_name, c)
                    html_email = loader.render_to_string(
                        html_email_template_name,
                        c
                    )
                    send_mail(
                        subject,
                        email,
                        config.EMAIL_FROM,
                        [user.email],
                        fail_silently=config.EMAIL_FAIL_SILENTLY,
                        html_message=html_email
                    )

                    reset(username=user.username)


                return self.form_valid(form)

            elif config.ELGG_URL:

                elgg_urls =  config.ELGG_URL.splitlines()

                for url in elgg_urls:
                    # Verify user exists in Elgg
                    valid_user_request = requests.post(
                        url + "/services/api/rest/json/",
                        data={
                            'method': 'pleio.userexists',
                            'user': email
                        }
                    )

                    valid_user_json = json.loads(valid_user_request.text)
                    valid_user_result = valid_user_json["result"] if 'result' in valid_user_json else []
                    valid_user = valid_user_result["valid"] if 'valid' in valid_user_result else False
                    name = valid_user_result["name"] if 'name' in valid_user_result else email

                    # If exists in Elgg, create local user
                    if valid_user is True:
                        user = User.objects.create_user(
                            name=name,
                            email=email.lower(),
                            accepted_terms=True,
                            receives_newsletter=True
                        )
                        user.is_active = True
                        user.save()
                        service_mesh_message('user.new', json.dumps({
                            'name': user.name,
                            'email': user.email,
                            'gcID': user.id,
                            'isAdmin': user.is_admin
                        }))
                        c = {
                            'domain': request.META['HTTP_HOST'],
                            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                            'user': user,
                            'token': default_token_generator.make_token(user),
                            'protocol': request.is_secure() and "https" or "http",
                            'app': config
                        }
                        subject_template_name = 'emails/reset_password_subject.txt'
                        email_template_name = 'emails/reset_password.txt'
                        html_email_template_name = 'emails/reset_password.html'
                        subject = loader.render_to_string(subject_template_name, c)
                        subject = ''.join(subject.splitlines())
                        email = loader.render_to_string(email_template_name, c)
                        html_email = loader.render_to_string(html_email_template_name, c)
                        send_mail(
                            subject,
                            email,
                            config.EMAIL_FROM,
                            [user.email],
                            fail_silently=config.EMAIL_FAIL_SILENTLY,
                            html_message=html_email
                        )

                        return self.form_valid(form)

                else:
                    form.add_error(None, _("No user is associated with this email address."))
                    return self.form_invalid(form)

            else:
                form.add_error(None, _("No user is associated with this email address."))
                return self.form_invalid(form)

        else:
            form.add_error(None, _("Please provide a valid email address."))
            return self.form_invalid(form)


class EmailField(forms.EmailField):
    def clean(self, value):
        super(EmailField, self).clean(value)
        if not is_email_valid(value):
            raise forms.ValidationError(
                _("Your email address is not allowed.")
            )

        found_user = User.objects.filter(email__iexact=value, is_active=True)
        if found_user.exists():
            raise forms.ValidationError(_("This email is already registered."))
        else:
            return value


class RegisterForm(forms.Form):
    error_messages = {
        'password_mismatch': _("The two password fields didn't match."),
        'captcha_mismatch': 'captcha_mismatch',
        'unique_email': _('This email is already in use.'),
    }

    name = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={'aria-labelledby': 'error_name'})
    )
    email = EmailField(
        required=True,
        widget=forms.TextInput(attrs={'aria-labelledby': 'error_email'})
    )
    password1 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={
            'aria-labelledby': 'error_password1',
            'aria-describedby': 'pwd-reqs'
        })
    )
    password2 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={
            'aria-labelledby': 'error_password2'
        })
    )
    accepted_terms = forms.BooleanField(required=True)
    receives_newsletter = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)

        if config.RECAPTCHA_ENABLED:
            self.fields["g-recaptcha-response"] = forms.CharField()

    def clean_email(self):
        # Get the emails
        email = self.cleaned_data.get('email').lower()

        try:
            User.objects.get(email=email)
        except User.DoesNotExist:
            return email

        raise forms.ValidationError(
            self.error_messages['unique_email'],
            code='unique_email'
        )

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")

        password_validation.validate_password(
            self.cleaned_data.get('password1')
        )
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                self.error_messages['password_mismatch'],
                code='password_mismatch',
            )

        return password2

    def clean(self):
        super(RegisterForm, self).clean()
        re_response = self.cleaned_data.get('g-recaptcha-response')
        if not verify_captcha_response(re_response):
            raise forms.ValidationError(
                self.error_messages['captcha_mismatch'],
                code='captcha_mismatch',
            )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('name', 'email', 'receives_newsletter',)
    def clean_email(self):
        return self.cleaned_data.get('email').lower()


class LabelledLoginForm(AuthenticationForm):
    username = forms.CharField(
        required=True,
        max_length=254,
        widget=forms.TextInput(attrs={
            'id': 'id_auth-username',
            'aria-labelledby': 'error_login'
        })
    )
    password = forms.CharField(
        required=True,
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'off'})
    )
    def clean(self):
        username = self.cleaned_data.get('username').lower()
        password = self.cleaned_data.get('password')

        credentials={
            'username': username,
            'password': password,
            'auth-username': username,
            'auth-password': password
        }

        if username is not None and password:
            self.user_cache = authenticate(self.request, **credentials)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

class PleioAuthenticationTokenForm(AuthenticationTokenForm):
    otp_token = forms.IntegerField(label=_("Token"), widget=forms.TextInput)


class PleioTOTPDeviceForm(TOTPDeviceForm):
    token = forms.IntegerField(label=_("Token"), widget=forms.TextInput)


class ChangePasswordForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        super(ChangePasswordForm, self).__init__(*args, **kwargs)

    error_messages = {
        'invalid_password': _("The password is invalid."),
        'password_mismatch': _("The two password fields didn't match."),
    }

    old_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={
            'aria-labelledby': 'error_id_old_password'
        })
    )
    new_password1 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={
            'aria-labelledby': 'error_id_new_password1'
        })
    )
    new_password2 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={
            'aria-labelledby': 'error_id_new_password2'
        })
    )

    def clean_old_password(self):
        old_password = self.cleaned_data.get("old_password")
        user = authenticate(self.request, username=self.user.email, password=old_password)

        if user is None:
            raise forms.ValidationError(
                self.error_messages['invalid_password'],
                code='invalid_password',
            )

        return old_password

    def clean_new_password2(self):
        new_password1 = self.cleaned_data.get("new_password1")
        new_password2 = self.cleaned_data.get("new_password2")

        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError(
                self.error_messages['password_mismatch'],
                code='password_mismatch',
            )

        password_validation.validate_password(
            self.cleaned_data.get('new_password2')
        )
        return new_password2


class ChooseSecurityQuestion(forms.Form):
    QUESTIONS1 = [
        ('', _('Please select one of the questions')),
        (1, _('What is your favourite board game?')),
        (2, _('Who is your favourite fictional character?')),
        (3, _('What is your least favourite chore?')),
    ]

    QUESTIONS2 = [
        ('', _('Please select one of the questions')),
        (4, _('What type of music do you dislike most?')),
        (5, _('What was your favourite TV show when you were a child?')),
        (6, _('Who was your best friend in kindergarten?')),
    ]

    QUESTIONS3 = [
        ('', _('Please select one of the questions')),
        (7, _(
            'If you won the lottery, what would be your first big purchase?'
        )),
        (8, _('What is the first movie you saw in theatres?')),
        (9, _('What was your first cell phone?')),
        (10, _('What movie do you know the most quotes from?'))
    ]

    question_one = forms.ChoiceField(choices=QUESTIONS1, initial=0)
    answer_one = forms.CharField(min_length=3, max_length=100)
    question_two = forms.ChoiceField(choices=QUESTIONS2, initial=0)
    answer_two = forms.CharField(min_length=3, max_length=100)
    question_three = forms.ChoiceField(choices=QUESTIONS3, initial=0)
    answer_three = forms.CharField(min_length=3, max_length=100)

    def clean(self):
        cleaned_data = super(ChooseSecurityQuestion, self).clean()
        question_one = cleaned_data.get('question_one')
        question_two = cleaned_data.get('question_two')
        question_three = cleaned_data.get('question_three')

        if question_one == question_two or question_one == question_three or \
                question_two == question_three:
            raise forms.ValidationError(
                _("The same question can not be used more than once")
            )


class AnswerSecurityQuestions(forms.Form):
        question_email = forms.CharField(required=False)
        answer_one = forms.CharField(max_length=100, initial="")
        q1 = forms.IntegerField(required=False)
        answer_two = forms.CharField(max_length=100, initial="")
        q2 = forms.IntegerField(required=False)

        def clean(self):
            cleaned_data = super(AnswerSecurityQuestions, self).clean()
            q1 = cleaned_data.get('q1')
            answer_one = cleaned_data.get('answer_one')
            q2 = cleaned_data.get('q2')
            answer_two = cleaned_data.get('answer_two')
            email = cleaned_data.get('question_email')

            user = User.objects.get(email=email)
            questions = user.securityquestions

            test = questions.check_answers(
                q1,
                answer_one.lower(),
                q2,
                answer_two.lower()
            )

            if not test:
                raise forms.ValidationError(_(
                    'One or more of your answers do not match'
                    ' the registered answers.'
                ))


class AppRemoveAccess(forms.Form):
    object_id = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(AppRemoveAccess, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(AppRemoveAccess, self).clean()
        object_id = cleaned_data.get('object_id')

        app_consent = UserConsent.objects.get(id=object_id)

        if app_consent.user_id != self.user.id:
            raise forms.ValidationError(_('Unable to remove access'))

class ResendValidation(forms.Form):
    email = forms.CharField(widget=forms.HiddenInput())
