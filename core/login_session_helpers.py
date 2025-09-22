import re
import warnings

from django.utils.translation import gettext_lazy as _
from django.contrib.gis.geoip2 import GeoIP2


BROWSERS = (
    (re.compile('Chrome'), _('Chrome')),
    (re.compile('Safari'), _('Safari')),
    (re.compile('Firefox'), _('Firefox')),
    (re.compile('Opera'), _('Opera')),
    (re.compile('IE'), _('Internet Explorer')),
)
DEVICES = (
    (re.compile('Android'), _('Android')),
    (re.compile('Linux'), _('Linux')),
    (re.compile('iPhone'), _('iPhone')),
    (re.compile('iPad'), _('iPad')),
    (re.compile('Mac OS X 10[._]9'), _('OS X Mavericks')),
    (re.compile('Mac OS X 10[._]10'), _('OS X Yosemite')),
    (re.compile('Mac OS X 10[._]11'), _('OS X El Capitan')),
    (re.compile('Mac OS X 10[._]12'), _('macOS Sierra')),
    (re.compile('Mac OS X'), _('OS X')),
    (re.compile('NT 5.1'), _('Windows XP')),
    (re.compile('NT 6.0'), _('Windows Vista')),
    (re.compile('NT 6.1'), _('Windows 7')),
    (re.compile('NT 6.2'), _('Windows 8')),
    (re.compile('NT 6.3'), _('Windows 8.1')),
    (re.compile('NT 10.0'), _('Windows 10')),
    (re.compile('Windows'), _('Windows')),
)

def get_device(value):
    browser = None
    for regex, name in BROWSERS:
        if regex.search(value):
            browser = name
            break

    device = None
    for regex, name in DEVICES:
        if regex.search(value):
            device = name
            break

    if browser and device:
        return _('%(browser)s on %(device)s') % {
            'browser': browser,
            'device': device
        }

    if browser:
        return browser

    if device:
        return device

    return None

def get_city(value):
    try:
        location = geoip() and geoip().city(value)
        city = location.get('city', '')
    except Exception as e:
        warnings.warn(str(e))
        city = ''

    return city

def get_lat_lon(value):
    try:
        location = geoip() and geoip().lat_lon(value)
    except Exception as e:
        warnings.warn(str(e))
        location = ''

    return location

def get_country(value):
    try:
        location = geoip() and geoip().country(value)
        country = location.get('country_name', '')
    except Exception as e:
        warnings.warn(str(e))
        country = ''

    return country

_geoip = None

def geoip():
    global _geoip
    if _geoip is None:
        try:
            _geoip = GeoIP2()
        except Exception as e:
            warnings.warn(str(e))
    return _geoip