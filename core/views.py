import urllib
import hashlib
import hmac
import random

from django.shortcuts import render, redirect
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from .forms import (
    RegisterForm,
    UserProfileForm,
    PleioTOTPDeviceForm,
    ChangePasswordForm,
    ChooseSecurityQuestion,
    AnswerSecurityQuestions,
    AppRemoveAccess,
    ResendValidation
)
from .models import User, PreviousLogin, SecurityQuestions
from django.urls import reverse
from constance import config
from base64 import b32encode
from binascii import unhexlify
from django_otp.util import random_hex
import django_otp

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import make_password
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from core.class_views import (
    PleioBackupTokensView,
    PleioSessionListView,
    PleioProfileView
)
from two_factor.views.profile import DisableView

from django.http import Http404, HttpResponseRedirect
from django.views.decorators.cache import never_cache
import time
from datetime import datetime
from oidc_provider.models import UserConsent

def home(request):
    if request.user.is_authenticated:
        return redirect('profile')

    return redirect('login')


def logout(request):
    auth.logout(request)
    return redirect('login')


def register(request):
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                user = User.objects.create_user(
                    name=data['name'],
                    email=data['email'],
                    password=data['password2'],
                    accepted_terms=data['accepted_terms'],
                    receives_newsletter=True
                )
            except Exception:
                user = User.objects.get(email=data['email'])

            if not user.is_active:
                user.send_activation_token(request)

            return redirect('register_complete')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})

def register_complete(request):
    return render(request, 'register_complete.html')


def register_activate(request, activation_token=None):
    if request.user.is_authenticated:
        return redirect('profile')

    user = User.activate_user(None, activation_token)

    if user:
        auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('profile')

    return render(request, 'register_activate.html')

def not_active_profile(request):
    email = request.session['email']

    if request.method == "POST":
        form = ResendValidation(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            found_user = User.objects.filter(email__iexact=data['email'])

            for user in found_user:
                user.send_activation_token(request)

            return render(request, 'registration/password_reset_not_active.html', { 'email': email, 'submit': True })
    else:
        return render(request, 'registration/password_reset_not_active.html', { 'email': email, 'submit': False })

@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save()
            form = UserProfileForm(instance=request.user)
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'profile.html', {'form': form})


def avatar(request):
    DEFAULT_AVATAR = '/static/images/user.svg'

    user = User.objects.get(id=request.GET['guid'])

    try:
        user = User.objects.get(id=int(request.GET['guid']))
        if user.avatar:
            return redirect('/media/' + str(user.avatar))
    except User.DoesNotExist:
        pass

    return redirect(DEFAULT_AVATAR)


def accept_previous_login(request, acceptation_token=None):
    try:
        PreviousLogin.accept_previous_logins(request, acceptation_token)
    except Exception:
        pass

    return redirect('profile')


def terms_of_use(request):
    return render(request, 'terms_of_use.html')


def security_questions(request):
    #bring user back to start
    if 'email' not in request.session:
        return redirect('password_reset')

    user = User.objects.get(email=request.session['email'])
    if hasattr(user, 'securityquestions'):
        questions = user.securityquestions
    else:
        questions = None
    has_questions = False if questions is None else True

    #pick 2 of 3 questions
    if has_questions:
        #save choices
        if 'picks' not in request.session:
            picks = [1,2,3]
            random.shuffle(picks)
            request.session['picks'] = picks
        else:
            picks = request.session['picks']
        picked_questions = questions.get_questions(request.session['picks'][0],request.session['picks'][1])
    else:
        picked_questions = {}
        picks = {}

    form = AnswerSecurityQuestions()
    if request.method == "POST":
        form = AnswerSecurityQuestions(request.POST)
        if form.is_valid():
            del request.session['email']
            del request.session['picks']
            return redirect(request.scheme + '://' + request.META['HTTP_HOST'] + '/reset-reinitialiser/' +
                urlsafe_base64_encode(force_bytes(user.pk)) + '/' +
                default_token_generator.make_token(user)
             )

    return render(request, 'registration/password_reset_questions.html', {
        'form': form,
        "has_questions": has_questions,
        "questions": picked_questions,
        "picks": picks
    })

@login_required
def security_pages(request, page_action=None):

    return render(request, 'security_pages.html', {
        'pass_reset_form': change_password_form(request, page_action),
        'security_questions': security_question(request),
        '2FA': two_factor_form(request, page_action),
        'user_session_form': user_sessions_form(request),
        'authorized_apps': authorized_apps(request)
    })

def change_password_form(request, page_action):
    if page_action == 'change-password':
        user = request.user
        form = ChangePasswordForm(request.POST, user=user, request=request)
        if form.is_valid():
            data = form.cleaned_data
            new_password2 = data['new_password2']
            user.set_password(data['new_password2'])
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, _('The password has been changed successfully.'))
    else:
        form = ChangePasswordForm()

    return form

def security_question(request):
    security_questions = {}
    return security_questions

@login_required
def set_security_question(request):

    form = ChooseSecurityQuestion()
    if request.method == 'POST':
        form = ChooseSecurityQuestion(request.POST)
        if form.is_valid():
            #check to see if user already set questions
            if hasattr(request.user, 'securityquestions'):
                questions = request.user.securityquestions
            else:
                questions = None

            data = form.cleaned_data
            if questions == None:
                new_question = SecurityQuestions.objects.create(
                    user=request.user,
                    question_1=data['question_one'],
                    answer_1=make_password(data['answer_one'].lower()),
                    question_2=data['question_two'],
                    answer_2=make_password(data['answer_two'].lower()),
                    question_3=data['question_three'],
                    answer_3=make_password(data['answer_three'].lower())
                )
                new_question.save()
            else:
                questions.question_1=data['question_one']
                questions.answer_1=make_password(data['answer_one'].lower())
                questions.question_2=data['question_two']
                questions.answer_2=make_password(data['answer_two'].lower())
                questions.question_3=data['question_three']
                questions.answer_3=make_password(data['answer_three'].lower())
                questions.save()

            messages.success(request, _('Security questions set. Your security questions and answers have been successfully saved.'))
            return redirect('security_pages')

    return render(request, 'security_pages_questions.html', { 'form': form })

def two_factor_form(request, page_action):
    two_factor_authorization =  {}
    if page_action == '2fa_setup-a2f_configuration':
        key = random_hex(20).decode('ascii')
        rawkey = unhexlify(key.encode('ascii'))
        b32key = b32encode(rawkey).decode('utf-8')

        request.session['tf_key'] = key
        request.session['django_two_factor-qr_secret_key'] = b32key

        two_factor_authorization = ({
            'form': PleioTOTPDeviceForm(key=key, user=request.user),
            'QR_URL': reverse('two_factor:qr')
        })
        two_factor_authorization['state'] = 'setup'

    elif page_action == '2fa_setupnext-a2f_configurationsuivante':
        key = request.session.get('tf_key')
        form = PleioTOTPDeviceForm(data=request.POST, key=key, user=request.user)
        if form.is_valid():
            device = form.save()
            django_otp.login(request, device)
            two_factor_authorization['default_device'] = True
            two_factor_authorization['show_state'] = True
        else:
            two_factor_authorization['form'] = form
            two_factor_authorization['QR_URL'] = reverse('two_factor:qr')
            two_factor_authorization['state'] = 'setup'

    elif page_action == '2fa_disable-a2f_desactiver':
        two_factor_authorization = DisableView.as_view(template_name='security_pages.html')(request).context_data
        two_factor_authorization['state'] = 'disable'

    elif page_action == '2fa_disableconfirm-a2f_desactiverconfirmer':
        two_factor_authorization = DisableView.as_view(template_name='security_pages.html')(request)
        two_factor_authorization['state'] = 'default'
        two_factor_authorization['show_state'] = 'true'

    elif page_action == '2fa_showcodes-a2f_afficherlescodes':
        two_factor_authorization = PleioBackupTokensView.as_view(template_name='backup_tokens.html')(request).context_data
        two_factor_authorization['default_device'] = 'true'
        two_factor_authorization['state'] = 'codes'
        two_factor_authorization['show_state'] = 'true'

    elif page_action == '2fa_generatecodes-a2f_genererdescodes':
        two_factor_authorization = PleioBackupTokensView.as_view(template_name='security_pages.html')(request).context_data
        two_factor_authorization['default_device'] = 'true'
        two_factor_authorization['show_state'] = 'true'
        two_factor_authorization['state'] = 'codes'

    else:
        two_factor_authorization = PleioProfileView.as_view(template_name='security_pages.html')(request).context_data
        two_factor_authorization['state'] = 'default'
        two_factor_authorization['show_state'] = 'true'

    return two_factor_authorization


def user_sessions_form(request):
    user_sessions = PleioSessionListView.as_view(template_name='security_pages.html')(request).context_data

    return user_sessions['object_list']

def authorized_apps(request):
    user_email = request.user.email
    authorized_apps = UserConsent.objects.filter(user__email=user_email)
    apps = []
    #Remove expired access apps from list
    for app in authorized_apps:
        if app.expires_at > datetime.now(app.expires_at.tzinfo):
            apps.append(app)
    return apps

def revoke_app_access(request):
    if request.method == "POST":
        form = AppRemoveAccess(request.user, request.POST)
        if form.is_valid():
            data = form.cleaned_data

            #Grab consent object
            app_consent = UserConsent.objects.get(id=data['object_id'])
            #Set new expiration time. Now - 12 hours to be safe
            app_consent.expires_at = (datetime.fromtimestamp(time.time() - 43200))
            app_consent.save()

            messages.success(request, (_("Application access has been removed")))

            return redirect('security_pages')

    return redirect('security_pages')


@never_cache
@login_required
def freshdesk_sso(request):

    if not request.user:
        raise Http404()

    name = request.user.name
    email = request.user.email
    dt = int(time.time())

    data = '{0}{1}{2}{3}'.format(name, config.FRESHDESK_SECRET_KEY, email, dt)
    generated_hash = hmac.new(
        config.FRESHDESK_SECRET_KEY.encode(),
        data.encode(),
        hashlib.md5
    ).hexdigest()

    return HttpResponseRedirect(
        config.FRESHDESK_URL
        + 'login/sso/?'
        + urllib.parse.urlencode({
            'name': name,
            'email': email,
            'timestamp': str(dt),
            'hash': generated_hash
        })
    )
