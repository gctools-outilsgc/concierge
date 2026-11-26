from django.contrib.admin import ModelAdmin
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from django.utils.text import slugify
from django.core import signing
from django.core.mail import send_mail
from django.contrib import admin
from django.contrib.sites.shortcuts import get_current_site
from django.db import models
from django.template.loader import render_to_string
from constance import config

from .helpers import unique_filepath
from .login_session_helpers import (
    get_city,
    get_country,
    get_device,
    get_lat_lon
)

class Manager(BaseUserManager):
    def create_user(self, email, name, password=None, accepted_terms=False,
                    receives_newsletter=True):
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=self.normalize_email(email),
            name=name
        )

        user.set_password(password)
        user.accepted_terms = accepted_terms
        user.receives_newsletter = receives_newsletter

        user.save(using=self._db)

        return user

    def create_superuser(self, email, name, password):
        user = self.create_user(
            email=self.normalize_email(email),
            name=name,
            password=password
        )

        user.is_admin = True
        user.is_active = True
        user.receives_newsletter = True

        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    objects = Manager()
    username = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255, unique=True)
    accepted_terms = models.BooleanField(default=False)
    receives_newsletter = models.BooleanField(default=True)
    avatar = models.ImageField(
        upload_to=unique_filepath,
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    REQUIRED_FIELDS = ['name']
    USERNAME_FIELD = 'email'

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self._get_unique_username()

        super(User, self).save(*args, **kwargs)

    def __str__(self):
        return self.email

    def _get_unique_username(self):
        max_length = User._meta.get_field('username').max_length
        username = slugify(self.email.split("@")[0])
        unique_username = username[:max_length]
        i = 1

        while User.objects.filter(username=unique_username).exists():
            unique_username = '{}-{}'.format(
                username[:max_length - len(str(i)) - 1],
                i
            )
            i += 1

        return unique_username

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def email_user(self, subject, message, **kwargs):
        send_mail(subject, message, config.EMAIL_FROM, [self.email], **kwargs)

    def send_activation_token(self, request):
        current_site = get_current_site(request)

        template_context = {
            'user': self,
            'activation_token': signing.dumps(obj=self.email),
            'protocol': 'https' if request.is_secure() else 'http',
            'domain': current_site.domain,
            'app': config
        }
        self.email_user(
            render_to_string('emails/register_subject.txt', template_context),
            render_to_string('emails/register.txt', template_context),
            html_message=render_to_string(
                'emails/register.html',
                template_context
            ),
            fail_silently=config.EMAIL_FAIL_SILENTLY
        )

    def activate_user(self, activation_token):
        try:
            email = signing.loads(
                activation_token,
                max_age=config.ACCOUNT_ACTIVATION_DAYS * 86400
            )

            if email is None:
                return None

            self = User.objects.get(email=email)

            if self.is_active:
                return None

            self.is_active = True
            self.save()
            
            return self

        except (signing.BadSignature, User.DoesNotExist):
            return None

    def check_users_previous_logins(self, request):
        session = request.session

        try:
            login = self.previous_logins.get(
                ip=session.ip,
                user_agent=get_device(session.user_agent)
            )
            login.update_previous_login(request)
            return True
        except PreviousLogin.DoesNotExist:
            PreviousLogin.add_known_login(request, self)
            if self.receives_newsletter is True:
                self.send_suspicious_login_message(request)
            return False

    def logged_in_previously(self, request):
        # check whether user has previously logged in from this location and
        # using this device
        session = request.session

        login = self.previous_logins.filter(
            ip=session.ip,
            user_agent=get_device(session.user_agent)
        )

        known_login = (login.count() > 0)

        if not known_login:
            # request.user is atm still "Anonymoususer", so have to add self as
            # second arg
            PreviousLogin.add_known_login(request, self)
        else:
            login[0].update_previous_login(request)

        login = login.filter(confirmed_login=True)
        confirmed_login = (login.count() > 0)

        return confirmed_login

    def send_suspicious_login_message(self, request):
        session = request.session
        current_site = get_current_site(request)

        template_context = {
            'user': self,
            'city': get_city(session.ip),
            'country': get_country(session.ip),
            'user_agent': session.user_agent,
            'protocol': 'https' if request.is_secure() else 'http',
            'domain': current_site.domain,
            'app': config
        }

        self.email_user(
            render_to_string(
                'emails/suspicious_login_subject.txt',
                template_context
            ),
            render_to_string(
                'emails/suspicious_login.txt',
                template_context
            ),
            html_message=render_to_string(
                'emails/suspicious_login.html',
                template_context
            ),
            fail_silently=config.EMAIL_FAIL_SILENTLY
        )

    @property
    def is_staff(self):
        return self.is_admin

    @property
    def is_superuser(self):
        return self.is_admin


from django.contrib.auth.admin import UserAdmin  # noqa


class UserAdmin(UserAdmin):
    search_fields = ModelAdmin.search_fields + ('username', 'name', 'email',)
    list_filter = ModelAdmin.list_filter + ('is_active', 'is_admin',)
    list_display = ModelAdmin.list_display + ('is_active', 'id',)
    filter_horizontal = ()
    ordering = ('-id', )
    fieldsets = add_fieldsets = (
        (None, {
            'fields': ('last_login', 'name', 'email', 'password', 'avatar',)
        }),
        ('Settings', {
            'fields': (
                'accepted_terms',
                'receives_newsletter',
                'is_active',
                'is_admin',
            )
        }),
    )

    def save_model(self,request, obj, form, change):
        obj.save()


class PreviousLogin(models.Model):
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='previous_logins'
    )
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.CharField(null=True, blank=True, max_length=200)
    city = models.CharField(null=True, blank=True, max_length=100)
    country = models.CharField(null=True, blank=True, max_length=100)
    latitude = models.DecimalField(max_digits=5, decimal_places=3, null=True)
    longitude = models.DecimalField(max_digits=6, decimal_places=3, null=True)
    last_login_date = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'ip', 'user_agent')

    def add_known_login(request, user):
        session = request.session

        lat_lon = get_lat_lon(session.ip)
        try:
            latitude = lat_lon[0]
            longitude = lat_lon[1]
        except Exception:
            latitude = None
            longitude = None

        login = PreviousLogin.objects.create(
            user=user,
            ip=session.ip,
            user_agent=get_device(session.user_agent),
            city=get_city(session.ip),
            country=get_country(session.ip),
            latitude=latitude,
            longitude=longitude,
         )
        login.save()

    def update_previous_login(self, request):
        try:
            self.last_login_date = timezone.now()
            self.save()
        except Exception:
            pass


class PleioPartnerSite(models.Model):
    partner_site_url = models.URLField(null=False, db_index=True)
    partner_site_name = models.CharField(null=False, max_length=200)
    partner_site_logo_url = models.URLField(null=False)

    def __str__(self):
        return self.partner_site_name


class SecurityQuestions(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True
    )
    question_1 = models.CharField(max_length=255)
    question_2 = models.CharField(max_length=255)
    question_3 = models.CharField(max_length=255)
    answer_1 = models.CharField(max_length=255)
    answer_2 = models.CharField(max_length=255)
    answer_3 = models.CharField(max_length=255)

    def get_questions(self, q1, q2):
        questions = [0, 0]

        if q1 == 1:
            questions[0] = self.question_1
        elif q1 == 2:
            questions[0] = self.question_2
        else:
            questions[0] = self.question_3

        if q2 == 1:
            questions[1] = self.question_1
        elif q2 == 2:
            questions[1] = self.question_2
        else:
            questions[1] = self.question_3

        return questions

    def get_answers(self, q1, q2):
        answers = [0, 0]

        if q1 == 1:
            answers[0] = self.answer_1
        elif q1 == 2:
            answers[0] = self.answer_2
        else:
            answers[0] = self.answer_3

        if q2 == 1:
            answers[1] = self.answer_1
        elif q2 == 2:
            answers[1] = self.answer_2
        else:
            answers[1] = self.answer_3

        return answers

    def check_answers(self, q1, a1, q2, a2):
        answers = self.get_answers(q1, q2)
        if check_password(a1, answers[0]) and check_password(a2, answers[1]):
            result = True
        else:
            result = False
        return result


admin.site.register(User, UserAdmin)
admin.site.register(PleioPartnerSite)
