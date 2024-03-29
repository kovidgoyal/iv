#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import argparse
import mimetypes
import os
import sys
from gettext import gettext as _

from PyQt6.QtCore import QFileSystemWatcher, Qt, QTimer, QLoggingCategory
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from .constants import appname
from .view import View, file_metadata, path_to_url, setup_profile


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
        self.view = View(self)
        self.view.set_title.connect(self.set_title)
        self.view.refresh_all.connect(self.refresh_all)
        self.setCentralWidget(self.view)
        self.files = files
        self.directories = {os.path.dirname(f['path']) for f in files.values()}
        self.file_watcher = QFileSystemWatcher([f['path'] for f in files.values()] + list(self.directories), self)
        self.file_watcher.fileChanged.connect(self.file_changed, type=Qt.ConnectionType.QueuedConnection)
        self.file_watcher.directoryChanged.connect(self.directory_changed, type=Qt.ConnectionType.QueuedConnection)
        self.changed_files = set()
        self.changed_dirs = set()
        self.debounce_files, self.debounce_dirs = QTimer(), QTimer()
        for t in self.debounce_files, self.debounce_dirs:
            t.setInterval(1000), t.setSingleShot(True)
        self.debounce_files.timeout.connect(self.do_file_changed)
        self.debounce_dirs.timeout.connect(self.do_dir_changed)
        self.set_title(None)

    def closeEvent(self, ev):
        if self.view is not None:
            self.view.break_cycles()
            self.view.setParent(None)
        self.view = None
        self.setCentralWidget(None)
        sys.excepthook = sys.__excepthook__
        return super().closeEvent(ev)

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
        if not os.access(path, os.R_OK):
            self.files.pop(path_to_url(path), None)
        self.changed_files.add(path)
        self.debounce_files.start()

    def directory_changed(self, path):
        self.changed_dirs.add(path)
        self.debounce_dirs.start()

    def do_file_changed(self):
        files, self.changed_files = self.changed_files, set()
        for path in files:
            url = path_to_url(path)
            if url in self.files:
                try:
                    self.view.image_changed(url, file_metadata(path))
                except EnvironmentError:
                    del self.files[url]

    def do_dir_changed(self):
        dirs, self.changed_dirs = self.changed_dirs, set()
        all_files = {f['path'] for f in self.files.values()}
        added_files = set()
        for path in dirs:
            for f in files_from_dir(path):
                if f not in all_files:
                    added_files.add(f)
        for f in added_files:
            try:
                self.files[path_to_url(f)] = file_metadata(f)
            except EnvironmentError:
                continue
            else:
                d = os.path.dirname(f)
                self.directories.add(d)
                self.file_watcher.addPaths([d, f])
        self.view.refresh_files(self.files)

    def refresh_all(self):
        roots = set()
        for d in sorted(self.directories):
            for r in roots:
                if d.startswith(r):
                    break
            else:
                roots.add(d)
        files = {}
        for cf in original_files:
            try:
                files[path_to_url(cf)] = file_metadata(cf)
            except EnvironmentError:
                continue
        for f in roots:
            for cf in files_from_dir(f):
                try:
                    files[path_to_url(cf)] = file_metadata(cf)
                except EnvironmentError:
                    continue
        self.files = files
        self.directories = {os.path.dirname(f['path']) for f in files.values()}
        self.view.refresh_files(self.files)


original_files = set()


def main():
    args = parse_args()

    files = {}
    for f in args.files:
        if os.path.isdir(f):
            for cf in files_from_dir(f):
                try:
                    files[path_to_url(cf)] = file_metadata(cf)
                except EnvironmentError:
                    continue
        else:
            if is_supported_file_type(f):
                files[path_to_url(f)] = file_metadata(f)
                original_files.add(f)
            else:
                print(_('{} is not a supported file type').format(f), file=sys.stderr)
    if not files:
        raise SystemExit(_('No files to display were found'))
    app = QApplication([appname])
    app.setApplicationName(appname)
    app.setOrganizationName(appname)
    QLoggingCategory.setFilterRules('''\
qt.webenginecontext.info=false
''')
    setup_profile(files)
    w = MainWindow(files)
    w.show()
    app.exec()
