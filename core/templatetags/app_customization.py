from django import template
from django.conf import settings
from constance import config
from django.utils.translation import gettext

register = template.Library()


@register.simple_tag()
def show_customizations_bg_image():
    bg_image = config.APP_BACKGROUND_IMAGE
    if not bg_image:
        return ' none;'

    return f'url({settings.MEDIA_URL}{bg_image}); ' + {
            'T': 'background-repeat: repeat;',
            'C': 'background-repeat: no-repeat; background-size: cover;'
    }[config.APP_BACKGROUND_OPTIONS]

@register.filter(name='translate')
def translate(text):
    try:
        return gettext(text)
    except:
        return text
