"""Tests for the argparsed API of remindwindows"""

import string
import os
from pathlib import Path
from argparse import ArgumentParser
from hypothesis import given, note, assume
from hypothesis.strategies import text
from pytest import fixture, raises

from src.api import text_to_fpath, parse_args, run_args
from src.remindme import REMIND_DIR


rd = REMIND_DIR
@fixture(scope="session")
def move_reminders():
    """Fixture to backup and restore saved reminders while running tests."""
    rdt = REMIND_DIR.parent / '.tmpremindwindows'
    if rdt.exists():
        if rd.exists():
            for child in rd.iterdir():
                child.unlink()
        else:
            rd.mkdir()
    else:
        if rd.exists():
            REMIND_DIR.rename(rdt)
        rd.mkdir()

    yield rd
    for child in rd.iterdir():
        child.unlink()

    if rdt.exists():
        rd.rmdir()
        rdt.rename(rd)

def clean_reminders():
    """Remove tested reminders."""
    for child in rd.iterdir():
        child.unlink()

class ErrorRaisingArgumentParser(ArgumentParser):
    """Allows us to introspect ArgumentParser errors instead of them exiting"""
    def error(self, message):
        """Raise error in a viewable way."""
        raise ValueError(message)  # reraise an error


@given(text())
def test_fpath_alphanum(reminder_text):
    """Regardless of input, filename should be alphanumeric."""
    fpath = text_to_fpath(reminder_text).name
    name, ext = fpath.split('.')
    assert name.isalnum()

@given(text())
def test_ext(reminder_text):
    """The file extension should always be '.rem'"""
    fpath = text_to_fpath(reminder_text).name
    name, ext = fpath.split('.')
    assert ext == 'rem'

@given(text())
def test_len(reminder_text):
    """Length should always be less than or equal to 10 characters."""
    fpath = text_to_fpath(reminder_text).name
    name, ext = fpath.split('.')
    assert len(name) <= 10

@given(text())
def test_set_alphanum(reminder_text):
    """If the text has alphanumeric characters, they should be preserved in the filename."""
    fpath = text_to_fpath(reminder_text).name
    name, ext = fpath.split('.')

    if reminder_text == '':
        reminder_text = 'noname'
    orig = set([c for c in reminder_text if c.isalnum()])
    new = set([c for c in name if c.isalnum()])
    note(f"In: {reminder_text}")
    note(f"Orig: {orig}")
    note(f"New: {new}")
    if len(orig) > 1:
        assert orig == new

def test_add_number_to_end(move_reminders):
    """Adding the same reminder text should result in files that are numbered."""
    clean_reminders()
    for _ in range(3):
        run_args(parse_args(['add', 'reminder']))

    for child in REMIND_DIR.iterdir():
        assert str(child.name) in  ['reminder.rem', 'reminde000.rem', 'reminde001.rem']
        with child.open('r') as remind_file:
            assert remind_file.read() == 'reminder'


@given(fname=text(alphabet=string.ascii_letters, min_size=1))
def test_filename_collision(move_reminders, fname):
    """Adding with the same filename should raise an error."""
    clean_reminders()
    run_args(parse_args(['add', '-n', fname, "reminder1"], parser_class=ErrorRaisingArgumentParser))
    with raises(ValueError) as error:
        run_args(parse_args(['add', '-n', fname, "reminder text"],
                            parser_class=ErrorRaisingArgumentParser))
    assert "already a reminder" in str(error)

@given(text())
def test_add_valid_filename(filename):
    """
    Valid filenames should be added, and invalid ones should raise an error.
    Valid filenames should be able to be created.
    """
    clean_reminders()
    note(f"Filename: {filename}")

    wrongfuncs = [lambda s: s == '',
                  lambda s: not s.isprintable(),
                  lambda s: s.isdigit(),
                  lambda s: '/' in s,
                  lambda s: '*' in s,
                  lambda s: '.' in s,
                  lambda s: s.startswith('+'),
                  lambda s: s.startswith('-'),
                  lambda s: '\\' in s]

    wrong = False
    for func in wrongfuncs:
        if func(filename):
            wrong = True
            with raises(ValueError):
                parse_args(['add', '-n', filename, "The Reminder Text"],
                           parser_class=ErrorRaisingArgumentParser)
            return

    if not wrong:
        tmpdir = Path('tmp')
        tmpdir.mkdir()
        os.chdir(tmpdir)

        path = Path(filename)
        path.touch()
        path.unlink()

        os.chdir('..')
        tmpdir.rmdir()


@given(text())
def test_rejects_invalid_reminders(reminder):
    """
    Empty and unprintable reminders should be rejected.
    All other reminders should be able to be added.
    """
    clean_reminders()
    note(f"Reminder: {reminder}")
    assume(not reminder.startswith('-'))

    wrongfuncs = [(lambda s: s == '', "empty"),
                  (lambda s: not s.isprintable(), "printable")]

    wrong = False
    for func, err_str in wrongfuncs:
        if func(reminder):
            wrong = True
            with raises(ValueError) as error:
                parsed = parse_args(['add', reminder], parser_class=ErrorRaisingArgumentParser)
            assert err_str in str(error)

    if not wrong:
        parsed = parse_args(['add', reminder])
        assert reminder == parsed.reminder

        tmpdir = Path('tmp')
        tmpdir.mkdir()
        os.chdir(tmpdir)

        path = Path(parsed.fpath)
        path.touch()
        path.unlink()

        os.chdir(Path('..'))
        tmpdir.rmdir()
