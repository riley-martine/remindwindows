#!/usr/bin/env python3
"""Core functionality for remindwindows"""

import sys
from pathlib import Path
import re
import hashlib
import signal
import lockfile
import daemon
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QDesktopWidget,
                             QHBoxLayout, QVBoxLayout, QLabel)
from PyQt5.QtGui import QFont
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

REMIND_DIR = Path.home().joinpath('.remindwindows')
if REMIND_DIR.exists():
    if REMIND_DIR.is_dir():
        pass
    else:
        print(f"Reserved directory {str(REMIND_DIR)} exists as a file. Exiting.")
        sys.exit(1)
else:
    REMIND_DIR.mkdir()


def text_to_fpath(text):
    """Turns a reminder text into a suitable filename."""
    EXTENSION = ".rem"
    MAX_LEN = 20        # Not including extension

    pattern = re.compile(r'[\W_]+', re.UNICODE) # Restrict to alphanumeric
    alphanum = pattern.sub("", text)
    shortened = alphanum[:MAX_LEN]             # Restrict length
    if len(shortened) < 1:                     # If the reminder is something silly like "@@@@@"
        shortened = hashlib.sha1(text.encode("utf8")).hexdigest()[:MAX_LEN]
    fname = shortened + EXTENSION
    fpath = REMIND_DIR.joinpath(fname)         # Create path

    # We should add a number to the end of the filename if it already exists
    num_rems = 0
    WIDTH = 3 # Digits
    while fpath.exists():
        fname = shortened[:MAX_LEN-WIDTH] + str(num_rems).zfill(WIDTH) + EXTENSION
        fpath = REMIND_DIR.joinpath(fname)
        num_rems += 1

    return fpath


class Reminder(QWidget):
    """QWidget that has a path, can be deleted, and displays itself."""
    text = ""
    path = None
    label = None

    def __init__(self, path):
        self.path = path
        with path.open() as reminder_file:
            self.text = reminder_file.read()

    def launch(self):
        """Launch the widget."""
        super().__init__()
        self.init_ui()

    def __repr__(self):
        return self.text

    def delete(self):
        """Delete reminder file and close widget."""
        self.path.unlink()
        self.close()

    def init_ui(self):
        """Create the UI for our widget."""
        self.label = QLabel(self.text, self)
        font = QFont("Mono", 12, QFont.Bold)
        self.label.setFont(font)

        donebtn = QPushButton("Done", self)
        laterbtn = QPushButton("Later", self)
        donebtn.clicked.connect(self.close)
        laterbtn.clicked.connect(self.close)

        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(donebtn)
        hbox.addWidget(laterbtn)

        vbox = QVBoxLayout()
        vbox.addStretch(1)
        vbox.addWidget(self.label, Qt.AlignTop)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

        self.resize(250, 150)
        self.center()
        self.setWindowTitle(self.text)
        self.show()

    def center(self):
        """Center widget on screen."""
        # TODO place the window in unoccupied position
        geometry = self.frameGeometry()
        center = QDesktopWidget().availableGeometry().center()
        geometry.moveCenter(center)
        self.move(geometry.topLeft())


def add_reminder(text):
    """Create a reminder file with text $text."""
    textpath = text_to_fpath(text)
    textpath.touch()
    with textpath.open('w') as reminder_file:
        reminder_file.write(text)

def get_current_reminders():
    """Get a list of Reminder objects for all current reminders."""
    return [Reminder(r) for r in REMIND_DIR.iterdir() if str(r).endswith('.rem')]


class RemindHandler(FileSystemEventHandler, QThread):
    """Handles file events from watchdog being passed to our application."""
    created = pyqtSignal(str)
    deleted = pyqtSignal(str)
    path = None

    def __init__(self, path):
        super(RemindHandler, self).__init__()
        self.path = path

    def on_created(self, event):
        if event.src_path.endswith('.rem'): # Ignore swap files etc
            self.created.emit(event.src_path)

    def on_deleted(self, event):
        if event.src_path.endswith('.rem'):
            self.deleted.emit(event.src_path)


class FileCreatedWatcher(QThread):
    """Creates and runs observer."""
    path = None
    observer = None
    event_handler = None

    def __init__(self, path):
        super(FileCreatedWatcher, self).__init__()
        self.path = path
        self.observer = Observer()
        self.event_handler = RemindHandler(self.path)
        self.observer.schedule(self.event_handler, self.path)
        self.observer.start()

    def run(self):
        """Do nothing."""
        pass

    def get_emitter(self):
        """Get the event handler."""
        return self.event_handler


class RemindApplication(QApplication):
    """Core application that handles creating watcher and managing active reminders."""
    watcher = None
    reminders = []

    def __init__(self, args):
        super(RemindApplication, self).__init__(args)

        path = str(REMIND_DIR)

        self.watcher = FileCreatedWatcher(path)
        self.watcher.get_emitter().created.connect(self.file_created)
        self.watcher.get_emitter().deleted.connect(self.file_deleted)

        self.reminders = get_current_reminders()
        for reminder in self.reminders:
            reminder.launch()

    @pyqtSlot(str)
    def file_created(self, src_path):
        """Add a new reminder when reminder file is created, or update existing if modified."""
        #print(src_path + " "+ str(bool((self.is_existing_reminder(src_path)))))
        reminder = self.is_existing_reminder(src_path)
        if not reminder:
            reminder = Reminder(Path(src_path))
            reminder.launch()
            self.reminders.append(reminder)
        else:
            # TODO make this update instead of re-initialize
            reminder.close()
            self.reminders.remove(reminder)
            new_reminder = Reminder(Path(src_path))
            new_reminder.launch()
            self.reminders.append(new_reminder)

    @pyqtSlot(str)
    def file_deleted(self, src_path):
        """Remove Reminder if its file is deleted."""
        reminder = self.is_existing_reminder(src_path)
        reminder.close()
        self.reminders.remove(reminder)

    def is_existing_reminder(self, path):
        """If a passed path is a reminder, return the Reminder corresponding to it, else False."""
        for reminder in self.reminders:
            if reminder.path == Path(path):
                return reminder
        return False


def do_main_program(args):
    """Run main body of program. This is a function so we can daemonize."""
    app = RemindApplication(args)
    sys.exit(app.exec_())


def program_cleanup():
    """Do any cleanup needed for the program."""
    pass

def reload():
    """Reload the program."""
    pass

if __name__ == "__main__":
    PIDFILE = '/tmp/remindwindows.pid'
    if Path(PIDFILE+'.lock').exists():
        print("Error: remindwindows already running!")
        sys.exit(1)

    context = daemon.DaemonContext(
       	pidfile=lockfile.FileLock(PIDFILE))

    context.signal_map = {
        signal.SIGTERM: program_cleanup,
        signal.SIGHUP: 'terminate',
        signal.SIGUSR1: reload,
    }

    do_main_program(sys.argv)
    #with context:
    #    do_main_program(sys.argv)
