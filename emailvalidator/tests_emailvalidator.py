"""
Registration form validation tests using emailvalidator app
"""
from django.test import TransactionTestCase
from constance.test import override_config
from unittest import mock

from .validator import is_email_valid


@override_config(ELGG_URL='')
class EmailValidatorAnyTestCase(TransactionTestCase):
    """
    Run tests when the database allows any email address
    """
    fixtures = ['emailvalidator-any.json']

    def test_valid(self):
        """
        Test email addresses that should be valid
        """
        self.assertIs(is_email_valid("anyone@anywhere.net"), True)


@override_config(ELGG_URL='')
class EmailValidatorGoCTestCase(TransactionTestCase):
    """
    Run tests when the database only accepts GoC addresses
    """
    fixtures = ['emailvalidator-goc.json']

    def test_valid(self):
        """
        Test email addresses that should be valid
        """
        self.assertIs(is_email_valid("someone@canada.ca"), True)
        self.assertIs(is_email_valid("someone@dept.gc.ca"), True)

    def test_invalid(self):
        """
        Test email addresses that should be invalid
        """
        self.assertIs(is_email_valid("anyone@anywhere.net"), False)
        self.assertIs(is_email_valid("invalid@gc.ca"), False)
        self.assertIs(is_email_valid("invalid@dept.gc.g.ca"), False)

@override_config(ELGG_URL='gccollab.local')
class EmailValidatorELGG(TransactionTestCase):
    """
    Run tests when the database only accepts GoC addresses
    and include elgg site invite checks
    """
    class trueResponseJSON():
        text='{"result": true}'
    class falseResponseJSON():
        text='{"result": false}'

    fixtures = ['emailvalidator-goc.json']

    def test_valid(self):
        """
        Test email addresses that should be valid
        """

        with mock.patch('requests.post', return_value=self.trueResponseJSON()):
            self.assertIs(is_email_valid("someone@mydomain.ca"), True)
            self.assertIs(is_email_valid("someone@canada.ca"), True)

        with mock.patch('requests.post', return_value=self.falseResponseJSON()):
            self.assertIs(is_email_valid("someone@canada.ca"), True)
            self.assertIs(is_email_valid("someone@dept.gc.ca"), True)


    def test_invalid(self):
        """
        Test email addresses that should be valid
        """

        with mock.patch('requests.post', return_value=self.falseResponseJSON()):
            self.assertIs(is_email_valid("someone@mydomain.ca"), False)
            self.assertIs(is_email_valid("anyone@anywhere.net"), False)
            self.assertIs(is_email_valid("invalid@gc.ca"), False)
