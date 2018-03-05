#!/usr/bin/env python3
"""API interface for remindwindows."""

import argparse
import sys
import re
import hashlib
import subprocess
from pathlib import Path
import tabulate
try:
    from remindme import REMIND_DIR
except ModuleNotFoundError:
    from .remindme import REMIND_DIR


class DefaultName(argparse.Action):
    """Have a default filename that is created from the reminder argument."""
    def __call__(self, parser, namespace, values, option_string=None):
        namespace.fpathdefault = text_to_fpath(values)
        namespace.reminder = values

def parse_args(args, parser_class=argparse.ArgumentParser):
    """Parse CLI arguments via argparse and return the parsed args."""
    parser = parser_class(description="Display reminders as persistent windows")
    subparsers = parser.add_subparsers(help="sub-command help", dest="cmd")

    parser_add = subparsers.add_parser('add', help='Add a New Reminder')
    parser_add.add_argument('reminder', type=reminder_string, action=DefaultName,
                            help='The text of the reminder')
    parser_add.add_argument('-n', '--filename', type=not_reminder, required=False,
                            dest='fpath',
                            help='The filename you want to use. ".rem" will be appended.')

    parser_list = subparsers.add_parser('list', aliases=['ls'], help='List reminder files')

    parser_show = subparsers.add_parser('show', aliases=['cat'],
                                        help='Show a reminder, by filename or index.')
    parser_show.add_argument('file', type=is_reminder,
                             help='The filename or index of the reminder you want to view')

    parser_delete = subparsers.add_parser('delete', aliases=['rm', 'del'],
                                          help='Delete a reminder file')
    parser_delete.add_argument('files', type=is_reminder, nargs='*',
                               help='The filename(s) or index(es) of the reminder(s) you\
                               want to delete')
    parser_delete.add_argument('-f', '--force', action='store_true',
                               help='Do not prompt for deletion')

    parser_edit = subparsers.add_parser('edit', aliases=['vim'], help='Edit an existing reminder')
    parser_edit.add_argument('file', type=is_reminder,
                             help='The filename or index of the reminder you want to edit')

    if not args:
        parser.print_help()
        sys.exit(1)

    parsed = parser.parse_args(args)
    if hasattr(parsed, 'fpath') and parsed.fpath == None:
        parsed.fpath = parsed.fpathdefault
    return parsed


def run_args(params):
    """Evaluate the arguments passed and run the functions for them."""
    if params.cmd == 'add':
        if params.fpath is None:
            params.fpath = text_to_fpath(params.reminder)
        add_reminder(params.reminder, params.fpath)
    elif params.cmd in ['list', 'ls']:
        list_reminders()
    elif params.cmd in ['show', 'cat']:
        print(get_reminder(params.file))
    elif params.cmd in ['delete', 'rm', 'del']:
        delete_reminders(params.files, params.force)
    elif params.cmd in ['edit', 'vim']:
        edit_reminder(params.file)


def edit_reminder(path):
    """Open system editor for editing reminder."""
    # We /could/ use xdg-open here, but I like vim.
    subprocess.call(["vim", str(path)])

def get_reminder_filenames():
    """Get a list of all the reminder filenames, sorted alphabetically."""
    return sorted([f.name for f in REMIND_DIR.iterdir() if f.name.endswith('.rem')])


def is_reminder(file):
    """Returns boolean for whether reminder file exists"""
    path = resolve_reminder(file)
    if not path.exists():
        msg = f"{path.name} is not a reminder file."
        raise argparse.ArgumentTypeError(msg)
    return path

def not_reminder(file):
    """Detect if a file is not an existing reminder, but could be."""
    if file.isdigit():
        raise argparse.ArgumentTypeError("Cannot name reminder only digits.")
    path = resolve_reminder(file)
    if path.exists():
        msg = f"{path.name} is already a reminder file."
        raise argparse.ArgumentTypeError(msg)
    return path

def reminder_string(s):
    if s == '':
        raise argparse.ArgumentTypeError("Reminder cannot be empty.")
    if not s.isprintable():
        raise argparse.ArgumentTypeError("Reminder must be printable.")
    return s

def resolve_reminder(file):
    """
    Turn an index or filename into a path.
    Can be passed arguments in the form '0', 'remind.rem', 'remind'
    """
    badchars = ['/', '\\', '*']
    for char in badchars:
        if char in file:
            raise argparse.ArgumentTypeError(f"Filename cannot contain character '{char}'.")
    
    badstarts = ['-', '+', '.']
    for char in badstarts:
        if file.startswith(char):
            raise argparse.ArgumentTypeError(f"Filename cannot begin with  character '{char}'.")

    if file == '':
        raise argparse.ArgumentTypeError("Filename cannot be empty.")
    
    if not file.isprintable():
        raise argparse.ArgumentTypeError("Filename must be printable.")


    if file.endswith('.rem'):
        fpath = REMIND_DIR / file
    elif file.isdigit():
        try:
            fpath = REMIND_DIR / get_reminder_filenames()[int(file)]
        except IndexError:
            msg = "List index out of range"
            raise argparse.ArgumentTypeError(msg)
    else:
        fpath = REMIND_DIR / (file + '.rem')

    return Path(fpath)

def list_reminders():
    """Print a list of all the reminders, alongside their index."""
    files = get_reminder_filenames()
    indexed = list(zip(range(len(files)), files))
    print(tabulate.tabulate(indexed))

def delete_reminders(files, force):
    """Delete a reminder file."""
    if force:
        for file in files:
            file.unlink()
        return
    for file in files:
        delete_str = input(f"Delete {file.name}? (Y/n): ")
        if delete_str in ['y', 'Y', '']:
            file.unlink()

def get_reminder(path):
    """Given an index or reminder file, display it."""
    with path.open('r') as remind_file:
        return remind_file.read()

def text_to_fpath(text):
    """Turns a reminder text into a suitable filename.
    input: a string of any length
    return: a filename with only alphanumeric characters
    If no suitable shortening exists, uses a hash of the original string."""
    EXTENSION = ".rem"
    MAX_LEN = 10        # Not including extension

    pattern = re.compile(r'[\W_]+', re.UNICODE) # Restrict to alphanumeric
    alphanum = pattern.sub("", text)
    shortened = alphanum[:MAX_LEN]             # Restrict length
    if len(shortened) < 1 or shortened.isdigit(): # If the reminder is something silly like "@@@@@"
        if len(text) > 0:
            shortened = hashlib.sha1(text.encode("utf8", 'replace')).hexdigest()[:MAX_LEN]
        else:
            shortened = "noname"

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


def add_reminder(text, fpath):
    """Create a reminder file with text $text."""
    fpath.touch()
    with fpath.open('w') as reminder_file:
        reminder_file.write(text)


if __name__ == '__main__':
    parsed = parse_args(sys.argv[1:])
    print(parsed)
    run_args(parsed)
