#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import glob
import json
import subprocess
from functools import lru_cache

from PyQt5.Qt import QWebEngineView, QApplication, QWebEngineProfile, QWebEngineScript, QWebEnginePage, Qt, QUrl

from .constants import appname, cache_dir


# Settings {{{

def safe_makedirs(path):
    try:
        os.makedirs(path)
    except FileExistsError:
        pass


def create_script(name, src, world=QWebEngineScript.ApplicationWorld, injection_point=QWebEngineScript.DocumentCreation, on_subframes=True):
    script = QWebEngineScript()
    script.setSourceCode(src)
    script.setName(name)
    script.setWorldId(world)
    script.setInjectionPoint(injection_point)
    script.setRunsOnSubFrames(on_subframes)
    return script


@lru_cache()
def client_script():
    base = os.path.dirname(os.path.abspath(__file__))
    entry = os.path.join(base, 'main.pyj')
    mtime = 0
    for x in glob.glob(os.path.join(base, '*.pyj')):
        mtime = max(os.path.getmtime(x), mtime)

    compiled = os.path.join(base, 'main.js')
    if not os.path.exists(compiled) or os.path.getmtime(compiled) < mtime:
        build_cache = os.path.join(os.path.dirname(base), '.build-cache')
        print('Compiling RapydScript...')
        if subprocess.Popen(['rapydscript', 'compile', '-C', build_cache, '--js-version', '6', entry, '-o', compiled]).wait() != 0:
            raise SystemExit('Failed to compile the client side script, aborting')

    with open(compiled, 'rb') as f:
        src = f.read().decode('utf-8')
    return create_script(f.name, src)


def files_data(files):
    src = 'filelist = ' + json.dumps(list(files)) + ';'
    src += 'files = ' + json.dumps(dict(files)) + ';'
    return create_script('files-data.js', src)


def insert_scripts(profile, *scripts):
    sc = profile.scripts()
    for script in scripts:
        for existing in sc.findScripts(script.name()):
            sc.remove(existing)
    for script in scripts:
        sc.insert(script)


def create_profile(files, parent=None, private=False):
    if parent is None:
        parent = QApplication.instance()
    if private:
        ans = QWebEngineProfile(parent)
    else:
        ans = QWebEngineProfile(appname, parent)
        ans.setCachePath(os.path.join(cache_dir, appname, 'cache'))
        safe_makedirs(ans.cachePath())
        ans.setPersistentStoragePath(os.path.join(cache_dir, appname, 'storage'))
        safe_makedirs(ans.persistentStoragePath())
    ua = ' '.join(x for x in ans.httpUserAgent().split() if 'QtWebEngine' not in x)
    ans.setHttpUserAgent(ua)
    insert_scripts(ans, files_data(files), client_script())
    s = ans.settings()
    s.setDefaultTextEncoding('utf-8')
    s.setAttribute(s.FullScreenSupportEnabled, True)
    s.setAttribute(s.LinksIncludedInFocusChain, False)
    return ans
# }}}


def path_to_url(f):
    return bytes(QUrl.fromLocalFile(os.path.abspath(f)).toEncoded()).decode('utf-8')


def file_metadata(f):
    st = os.stat(f)
    return {'name': os.path.basename(f), 'mtime': st.st_mtime, 'size': st.st_size, 'ctime': st.st_ctime}


class Page(QWebEnginePage):

    def __init__(self, profile, parent):
        QWebEnginePage.__init__(self, profile, parent)

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        try:
            print(msg)
        except Exception:
            pass

    def check_for_messages_from_js(self, title):
        self.runJavaScript('try { window.get_messages_from_javascript() } catch(TypeError) {}',
                           QWebEngineScript.ApplicationWorld, self.messages_received_from_js)

    def messages_received_from_js(self, messages):
        if messages and messages != '[]':
            for msg in json.loads(messages):
                try:
                    func = getattr(self, msg['func'])
                except AttributeError:
                    continue
                func(msg)

    def calljs(self, func, *args, callback=None):
        js = 'window.{}.apply(this, {})'.format(func, json.dumps(args))
        if callback is None:
            self.runJavaScript(js, QWebEngineScript.ApplicationWorld)
        else:
            self.runJavaScript(js, QWebEngineScript.ApplicationWorld, callback)


class View(QWebEngineView):

    def __init__(self, profile, parent=None):
        QWebEngineView.__init__(self, parent)
        self._page = Page(profile, self)
        self.titleChanged.connect(self._page.check_for_messages_from_js, type=Qt.QueuedConnection)
        self.setPage(self._page)
        self.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')))
