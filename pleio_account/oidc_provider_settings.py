"""
OIDC provider settings
"""
from django.utils.translation import gettext as _
from oidc_provider.lib.claims import ScopeClaims
import requests
from constance import config

def userinfo(claims, user):
    """
    Populate claims dict.
    """
    retrys = 3

    claims['name'] = user.name
    claims['email'] = user.email

    if config.GRAPHQL_TRIGGER:
        return claimsfromprofiles(retrys, claims, user)
    else:
        return claims


def queryprofile(retry, user):
    success = False
    attempt = 0

    # Get rest of information from Profile as a Service
    query = """
    query($userID: ID!){
        profiles(gcID: $userID){
            name,
            avatar,
            email,
            mobilePhone,
            officePhone,
            titleEn,
            titleFr,
            address{
                streetAddress,
                city,
                postalCode,
                province,
                country
            }    
        }
    }  
    """
    variables = {
        "userID": user.id
    }

    while not success and attempt < retry:
        response = requests.post(config.GRAPHQL_ENDPOINT,
                                headers={"Content-Type":"application/json"}, json={'query':query, 'variables': variables})
        if not response.status_code == requests.codes.ok:
            attempt = attempt + 1
        else:
            success = True

    if not success:
        return None

    response = response.json()

    return response


def claimsfromprofiles(retry, claims, user):
    response = queryprofile(retry, user)

    if response is None:
        return claims

    try:
        profileclaims = claims
        response_address = response['data']['profiles'][0].get('address')

        profileclaims['picture'] = checkvalue(response['data']['profiles'][0].get('avatar'))
        if response['data']['profiles'][0].get('mobilePhone') is not None:
            profileclaims['phone_number'] = checkvalue(response['data']['profiles'][0].get('mobilePhone'))
        else:
            profileclaims['phone_number'] = checkvalue(response['data']['profiles'][0].get('officePhone'))

        if response_address is not None:

            if 'streetAddress' in response_address:
                profileclaims['address']['street_address'] = checkvalue(response_address.get('streetAddress'))
            if 'city' in response_address:
                profileclaims['address']['locality'] = checkvalue(response_address.get('city'))
            if 'province' in response_address:
                profileclaims['address']['region'] = checkvalue(response_address.get('province'))
            if 'postalCode' in response_address:
                profileclaims['address']['postal_code'] = checkvalue(response_address.get('postalCode'))
            if 'country' in response_address:
                profileclaims['address']['country'] = checkvalue(response_address.get('country'))
    except Exception:
        return claims

    return profileclaims

def titleclaims(retry, claims, user):
    response = queryprofile(retry, user)

    if response is None:
        return claims

    try:
        titleclaims = claims
        titleclaims['titleEn'] = checkvalue(response['data']['profiles'][0].get('titleEn'))
        titleclaims['titleFr'] = checkvalue(response['data']['profiles'][0].get('titleFr'))
    except Exception:
        return claims

    return titleclaims
    

def checkvalue(stringvalue):
    if stringvalue is not None:
        return stringvalue
    else:
        return ''


class CustomScopeClaims(ScopeClaims):
    info_modify_profile = (
        _('Profile Modification'),
        _('Ability to view and modify your profile information'),
    )

    def scope_modify_profile(self):
        # self.user - Django user instance.
        # self.userinfo - Dict returned by OIDC_USERINFO function.
        # self.scopes - List of scopes requested.
        # self.client - Client requesting this claims.
        dic = {
            'modify_profile': 'True',
            'detailed_profile': 'True'
        }

        return dic

    info_profile = (
        _('Basic profile'),
        _('Access to your name, email, avatar, and address'),
    )

    info_detailed_profile = (
        _('Detailed User profile'),
        _('Access to your name, email, avatar, address, and organization information'),
    )

    def scope_detailed_profile(self):
        dic = {
            'detailed_profile': 'True',
        }

        return dic

    info_titles = (
        _('Bilingual titles'),
        _('Access to your English and French title'),
    )

    def scope_titles(self):
        dic = {
            'titleEn': '',
            'titleFr': '',
        }

        if config.GRAPHQL_TRIGGER:
            return titleclaims(3, dic, self.user)
        else:
            return dic
