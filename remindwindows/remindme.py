#!/usr/bin/env python3
import sys
from pathlib import Path
import re
import string
import hashlib
import daemon
import time
import lockfile
import signal
from PyQt5.QtCore import Qt, QThread, QObject, QFileSystemWatcher, pyqtSignal, pyqtSlot
import PyQt5.QtCore
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
        print(f"Reserved directory {str(REMIND_DIR)} exists as a file. Exiting. ")
        sys.exit(1)
else:
    REMIND_DIR.mkdir()


def text_to_fpath(text):
    """Turns a reminder text into a suitable filename."""
    EXTENSION = ".rem"
    MAX_LEN = 20        # Not including extension

    pattern = re.compile('[\W_]+', re.UNICODE) # Restrict to alphanumeric
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
    text = ""
    path = None
    def __init__(self, path):
        self.path = path
        with path.open() as f:
            self.text = f.read()

    def launch(self):
        super().__init__()
        self.initUI()

    def __repr__(self):
        return self.text

    def delete(self):
        self.path.unlink()
        self.close()

    def initUI(self):
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
        # TODO place the window in unoccupied position
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
    

def add_reminder(text):
    """Create a reminder file with text $text."""
    textpath = text_to_fpath(text)
    textpath.touch()
    with textpath.open('w') as f:
        f.write(text)
    
def get_current_reminders():
    """Get a list of Reminder objects for all current reminders."""
    return [Reminder(r) for r in REMIND_DIR.iterdir() if str(r).endswith('.rem')]


class RemindHandler(FileSystemEventHandler, QThread):
    created = pyqtSignal(str)
    deleted = pyqtSignal(str)

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
    def __init__(self, path):
        super(FileCreatedWatcher, self).__init__()
        self.path = path
        self.observer = Observer()
        self.event_handler = RemindHandler(self.path)
        self.observer.schedule(self.event_handler, self.path)
        self.observer.start()
    
    def run(self):
        pass

    def getEmitter(self):
        return self.event_handler


class RemindApplication(QApplication):
    def __init__(self, args):
        super(RemindApplication, self).__init__(args)
        
        path = str(REMIND_DIR)

        self.watcher = FileCreatedWatcher(path)
        self.watcher.getEmitter().created.connect(self.file_created)
        self.watcher.getEmitter().deleted.connect(self.file_deleted)

        self.reminders = get_current_reminders()
        [r.launch() for r in self.reminders]
        
    @pyqtSlot(str)
    def file_created(self, src_path):
        #print(src_path + " "+ str(bool((self.is_existing_reminder(src_path)))))
        if not self.is_existing_reminder(src_path):
            r = Reminder(Path(src_path))
            r.launch()
            self.reminders.append(r)
        else:
            r = self.is_existing_reminder(src_path)
            r.close()
            self.reminders.remove(r)
            r = Reminder(Path(src_path))
            r.launch()
            self.reminders.append(r)

    @pyqtSlot(str)
    def file_deleted(self, src_path):
        r = self.is_existing_reminder(src_path)
        r.close()
        self.reminders.remove(r)

    def is_existing_reminder(self, path):
        for r in self.reminders:
            if r.path == Path(path):
                return r
        return False


def do_main_program(args):
    app = RemindApplication(args)
    
    sys.exit(app.exec_())

    

def program_cleanup():
    pass

def reload():
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
