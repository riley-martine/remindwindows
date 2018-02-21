#!/usr/bin/env python3
import sys
from pathlib import Path
import re
import string
import hashlib
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QDesktopWidget,
    QHBoxLayout, QVBoxLayout, QLabel)
from PyQt5.QtGui import QFont

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
    return [Reminder(r) for r in REMIND_DIR.iterdir()]

    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    rems = get_current_reminders()
    [r.launch() for r in rems]
    sys.exit(app.exec_())
