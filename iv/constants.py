#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys

from PyQt6.QtCore import QStandardPaths

appname = 'iv'

_plat = sys.platform.lower()
iswindows = 'win32' in _plat or 'win64' in _plat
isosx = 'darwin' in _plat
isfreebsd = 'freebsd' in _plat
isnetbsd = 'netbsd' in _plat
isdragonflybsd = 'dragonfly' in _plat
isbsd = isfreebsd or isnetbsd or isdragonflybsd
islinux = not(iswindows or isosx or isbsd)


def _get_cache_dir():
    if 'IV_CACHE_DIRECTORY' in os.environ:
        return os.path.abspath(os.path.expanduser(os.environ['IV_CACHE_DIRECTORY']))

    candidate = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    if not candidate and not iswindows and not isosx:
        candidate = os.path.expanduser(os.environ.get('XDG_CACHE_HOME', u'~/.cache'))
    if not candidate:
        raise RuntimeError(
            'Failed to find path for application cache directory')
    ans = os.path.join(candidate, appname)
    try:
        os.makedirs(ans)
    except FileExistsError:
        pass
    return ans
cache_dir = _get_cache_dir()
del _get_cache_dir


def _get_config_dir():
    if 'IV_CONFIG_DIRECTORY' in os.environ:
        return os.path.abspath(os.path.expanduser(os.environ['IV_CONFIG_DIRECTORY']))

    candidate = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.ConfigLocation)
    if not candidate:
        if isosx:
            candidate = os.path.expanduser('~/Library/Preferences')
        elif not iswindows:
            candidate = os.path.expanduser(os.environ.get('XDG_CONFIG_HOME', u'~/.config'))
    if not candidate:
        raise RuntimeError(
            'Failed to find path for application config directory')
    ans = os.path.join(candidate, appname)
    try:
        os.makedirs(ans)
    except FileExistsError:
        pass
    return ans
config_dir = _get_config_dir()
del _get_config_dir
