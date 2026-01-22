"""
Initialize the emailvalidator django application, and configure
"""
import re
import json

import requests
from constance import config
from core.helpers import str_to_bool

from .models import EmailRegExValidator


def is_email_valid(email):
    """
    Determines if the provided email is valid based on the regular expressions
    stored in the database.
    """
    validators = EmailRegExValidator.objects.all().filter(allow_all=False)
    regexes = [re.compile(r.regex, re.IGNORECASE) for r in validators]

    domains = EmailRegExValidator.objects.all().filter(allow_all=True)
    regexes += [
        re.compile(r"^.*@[\w.]*?" + r.regex + "$", re.IGNORECASE)
        for r in domains
    ]

    if any(regex.match(email) for regex in regexes):
        return True

    # Verify email address is in user invitation list
    if config.ELGG_URL:

        elgg_urls =  config.ELGG_URL.splitlines()

        for url in elgg_urls:
            valid_user_request = requests.post(
                url + "/services/api/rest/json/",
                data={
                    'method': 'pleio.invited',
                    'email': email
                }
            )

            valid_user_json = json.loads(valid_user_request.text)
            if str_to_bool(valid_user_json.get('result', False)):
                return True

    return False
