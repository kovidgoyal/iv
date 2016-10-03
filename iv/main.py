#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
import argparse
import mimetypes
from gettext import gettext as _

from PyQt5.Qt import QApplication, QMainWindow, QMessageBox, QFileSystemWatcher, Qt, QTimer

from .constants import appname
from .view import View, create_profile, path_to_url, file_metadata


def is_supported_file_type(f):
    t = mimetypes.guess_type(f)[0]
    return t and t.startswith('image/')


def files_from_dir(d):
    for dirpath, dirnames, filenames in os.walk(d):
        for f in filter(is_supported_file_type, filenames):
            yield os.path.join(dirpath, f)


def parse_args():
    parser = argparse.ArgumentParser(description=_('Browse/view images'))
    parser.add_argument('files', nargs='+',
                        help=_('Path to file or directory to display'))
    return parser.parse_args()


class MainWindow(QMainWindow):

    def __init__(self, files):
        QMainWindow.__init__(self)
        sys.excepthook = self.excepthook
        self.profile = create_profile(files)
        self.view = View(self.profile, self)
        self.view.set_title.connect(self.set_title)
        self.setCentralWidget(self.view)
        self.files = files
        self.file_watcher = QFileSystemWatcher([f['path'] for f in files.values()], self)
        self.file_watcher.fileChanged.connect(self.file_changed, type=Qt.QueuedConnection)
        self.changed_files = set()
        self.debounce = QTimer()
        self.debounce.setInterval(1000)
        self.debounce.timeout.connect(self.do_file_changed)
        self.debounce.setSingleShot(True)
        self.set_title(None)

    def excepthook(self, exctype, value, traceback):
        if exctype == KeyboardInterrupt:
            return
        sys.__excepthook__(exctype, value, traceback)
        try:
            msg = str(value)
        except Exception:
            msg = repr(value)
        QMessageBox.critical(self, _('Unhandled error'), msg)

    def set_title(self, val):
        title = val or (_('{} images').format(len(self.files)))
        title += ' :: ' + appname
        self.setWindowTitle(title)

    def file_changed(self, path):
        self.changed_files.add(path)
        self.debounce.start()

    def do_file_changed(self):
        files, self.changed_files = self.changed_files, set()
        for path in files:
            url = path_to_url(path)
            if url in self.files:
                try:
                    self.view.image_changed(url, file_metadata(path))
                except FileNotFoundError:
                    pass


def main():
    args = parse_args()

    files = {}
    for f in args.files:
        if os.path.isdir(f):
            for cf in files_from_dir(f):
                files[path_to_url(cf)] = file_metadata(cf)
        else:
            if is_supported_file_type(f):
                files[path_to_url(f)] = file_metadata(f)
            else:
                print(_('{} is not a supported file type').format(f), file=sys.stderr)
    if not files:
        raise SystemExit(_('No files to display were found'))
    app = QApplication([appname])
    app.setApplicationName(appname)
    app.setOrganizationName(appname)
    w = MainWindow(files)
    w.show()
    app.exec_()
