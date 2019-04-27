#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import glob
import json
import subprocess
from functools import lru_cache
from gettext import gettext as _

from PyQt5.Qt import Qt, QUrl, pyqtSignal, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineScript, QWebEngineProfile, QWebEnginePage

from .constants import appname, cache_dir, config_dir


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


def read_config():
    if not hasattr(read_config, 'config'):
        read_config.config = {
            'thumbnail_size': 128,
            'show_captions': True,
            'show_single_caption': True,
        }
        try:
            with open(os.path.join(config_dir, 'settings.json'), 'rb') as f:
                val = json.loads(f.read().decode('utf-8'))
                if isinstance(val, dict):
                    read_config.config.update(val)
        except FileNotFoundError:
            pass
    return read_config.config


def update_config(vals):
    c = read_config()
    c.update(vals)
    s = json.dumps(c, indent=2, sort_keys=True, ensure_ascii=False).encode('utf-8')
    with open(os.path.join(config_dir, 'settings.json'), 'wb') as f:
        f.write(s)


def files_data(files):
    src = 'image_data = ' + json.dumps(files) + ';'
    src += 'config = ' + json.dumps(read_config()) + ';'
    return create_script('files-data.js', src)


def insert_scripts(profile, *scripts):
    sc = profile.scripts()
    for script in scripts:
        for existing in sc.findScripts(script.name()):
            sc.remove(existing)
    for script in scripts:
        sc.insert(script)


def setup_profile(files):
    ans = QWebEngineProfile.defaultProfile()
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
    return {'name': os.path.basename(f), 'mtime': st.st_mtime, 'size': st.st_size, 'ctime': st.st_ctime, 'path': f}


class Page(QWebEnginePage):

    set_title = pyqtSignal(object)
    refresh_all = pyqtSignal()

    def __init__(self, parent):
        QWebEnginePage.__init__(self, parent)

    def break_cycles(self):
        self.set_title.disconnect()
        self.refresh_all.disconnect()
        self.setParent(None)

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
                del msg['func']
                func(msg)

    def calljs(self, func, *args, callback=None):
        js = 'window.{}.apply(this, {})'.format(func, json.dumps(args))
        if callback is None:
            self.runJavaScript(js, QWebEngineScript.ApplicationWorld)
        else:
            self.runJavaScript(js, QWebEngineScript.ApplicationWorld, callback)

    def update_settings(self, vals):
        update_config(vals)

    def showing_grid(self, data):
        self.set_title.emit(None)

    def showing_image(self, data):
        self.set_title.emit(os.path.basename(QUrl(data['url']).toLocalFile()))

    def unhandled_error(self, data):
        if False:  # disabled in case there is continuous looping error which can the dialog to popup infinitely
            QMessageBox.critical(self.parent(), _('Unhandled error'), data['msg'])

    def refresh_grid(self, data):
        self.refresh_all.emit()


class View(QWebEngineView):

    set_title = pyqtSignal(object)
    refresh_all = pyqtSignal()

    def __init__(self, parent=None):
        QWebEngineView.__init__(self, parent)
        self._page = Page(self)
        self._page.set_title.connect(self.set_title.emit)
        self._page.refresh_all.connect(self.refresh_all.emit)
        self.titleChanged.connect(self._page.check_for_messages_from_js, type=Qt.QueuedConnection)
        self.setPage(self._page)
        self.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')))
        self.renderProcessTerminated.connect(self.render_process_terminated)

    def break_cycles(self):
        self._page.break_cycles()
        self._page = None
        self.set_title.disconnect()
        self.refresh_all.disconnect()
        self.titleChanged.disconnect()
        self.renderProcessTerminated.disconnect()
        self.setPage(None)

    def render_process_terminated(self, termination_type, exit_code):
        if termination_type == QWebEnginePage.CrashedTerminationStatus:
            QMessageBox.critical(self.parent(), _('Render process crashed'), _(
                'The render process crashed while displaying the images with exit code: {}').format(exit_code))
        elif termination_type == QWebEnginePage.AbnormalTerminationStatus:
            QMessageBox.critical(self.parent(), _('Render process exited'), _(
                'The render process exited while displaying the images with exit code: {}').format(exit_code))

    def image_changed(self, key, metadata):
        self._page.calljs('image_changed', key, metadata)

    def refresh_files(self, files):
        self._page.calljs('refresh_files', files)
