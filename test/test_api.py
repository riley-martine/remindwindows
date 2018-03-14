"""Tests for the argparsed API of remindwindows"""
import string
import os
from pathlib import Path
from argparse import ArgumentParser
from unittest.mock import patch
from hypothesis import given, note, assume, reproduce_failure
from hypothesis.strategies import text
from pytest import fixture, raises
from tempfile import TemporaryDirectory

from src.api import text_to_fpath, parse_args, run_args, get_reminder, list_reminders
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

def get_parts(filename):
    """Get the name and extension of a filename."""
    name = '.'.join(filename.split('.')[:-1])
    ext = ''.join(filename.split('.')[-1:])
    return name, ext

def is_valid_filename(filename):
    wrongfuncs = [lambda s: s == '',
                  lambda s: not s.isprintable(),
                  lambda s: s.isdigit(),
                  lambda s: '/' in s,
                  lambda s: '*' in s,
                  lambda s: s.startswith('+'),
                  lambda s: s.startswith('-'),
                  lambda s: s.startswith('.'),
                  lambda s: '\\' in s]

    return not any([f(filename) for f in wrongfuncs])

@patch('subprocess.call', lambda x: x)
def test_subprocess_opens_vim(move_reminders):
    """Test that edit works as expected."""
    clean_reminders()
    namespace = parse_args(['add', 'reminder'])
    run_args(namespace)
    a = run_args(parse_args(['edit', 'reminder']))
    b = run_args(parse_args(['edit', '0']))
    c = run_args(parse_args(['edit', 'reminder.rem']))
    assert a == b
    assert b == c
    assert a == ['vim', str(REMIND_DIR / 'reminder.rem')]

@patch('builtins.input', lambda x: 'y')
def test_delete_reminder(capsys, move_reminders):
    """Test that delete actually deletes and prompts for deletion."""
    #TODO create test with lambda x: 'n'
    clean_reminders()
    run_args(parse_args(['add', 'reminder']))
    run_args(parse_args(['add', 'dothething']))
    run_args(parse_args(['add', 'another']))

    run_args(parse_args(['delete', 'reminder']))
    run_args(parse_args(['list']))
    out, err = capsys.readouterr()
    assert "reminder.rem" not in out
    assert "dothething.rem" in out
    assert "another.rem" in out

    run_args(parse_args(['delete', 'dothething.rem']))
    run_args(parse_args(['list']))
    out, err = capsys.readouterr()
    assert "dothething.rem" not in out
    assert "another.rem" in out

    run_args(parse_args(['delete', '0']))
    run_args(parse_args(['list']))
    out, err = capsys.readouterr()
    assert "No reminders found" in out

def test_delete_by_force(capsys, move_reminders):
    """Test that force flag does not prompt."""
    clean_reminders()
    run_args(parse_args(['add', 'reminder']))
    run_args(parse_args(['delete', '-f', 'reminder']))
    run_args(parse_args(['list']))
    out, err = capsys.readouterr()
    assert "No reminders found" in out

def test_list_when_no_reminders(capsys, move_reminders):
    """Test that when no reminders exist, we handle that."""
    clean_reminders()
    run_args(parse_args(['list']))
    out, err = capsys.readouterr()
    assert "No reminders found" in out

def test_list_reminder_names(capsys, move_reminders):
    """Test that reminders added are listed."""
    clean_reminders()
    run_args(parse_args(['add', 'reminder']))
    run_args(parse_args(['add', 'dothething']))
    run_args(parse_args(['add', 'another']))
    run_args(parse_args(['list']))
    out, err = capsys.readouterr()
    assert "2  reminder.rem" in out
    assert "1  dothething.rem" in out
    assert "0  another.rem" in out
    assert len(out.split('\n')) == 6

def test_print_help_when_no_arguments(capsys):
    """Test that when no arguments given to parse_args, help is printed."""
    run_args(parse_args([]))
    out, err = capsys.readouterr()
    assert "usage: " in out

@given(text())
def test_fpath_alphanum(reminder_text):
    """Regardless of input, filename should be alphanumeric."""
    fpath = text_to_fpath(reminder_text).name
    name, ext = get_parts(fpath)
    assert name.isalnum()

@given(text())
def test_ext(reminder_text):
    """The file extension should always be '.rem'"""
    fpath = text_to_fpath(reminder_text).name
    name, ext = get_parts(fpath)
    assert ext == 'rem'

@given(text())
def test_len(reminder_text):
    """Length should always be less than or equal to 10 characters."""
    fpath = text_to_fpath(reminder_text).name
    name, ext = get_parts(fpath)
    assert len(name) <= 10

@given(text())
def test_set_alphanum(reminder_text):
    """If the text has alphanumeric characters, they should be preserved in the filename."""
    fpath = text_to_fpath(reminder_text).name
    name, ext = get_parts(fpath)

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

@given(reminder_text=text(alphabet=string.printable, min_size=1).filter(lambda x: x.isprintable()))
def test_read_same_as_passed(move_reminders, reminder_text):
    """Test that the value passed to a reminder is the value read from a reminder."""
    clean_reminders()
    assume(not reminder_text.startswith('-'))

    parsed = parse_args(['add', reminder_text])
    run_args(parsed)
    with parsed.fpath.open('r') as reminder_file:
        assert reminder_file.read() == reminder_text
        assert get_reminder(parsed.fpath) == reminder_text

@given(reminder_text=text(alphabet=string.printable, min_size=1).filter(lambda x: x.isprintable()),
       filename=text(alphabet=string.printable, min_size=1).filter(lambda x: is_valid_filename(x)))
def test_show_reminder(capsys, move_reminders, reminder_text, filename):
    """Test that show works as expected."""
    clean_reminders()
    assume(not reminder_text.startswith('-'))

    add_parsed = parse_args(['add', '-n', 'A'+filename, 'A'+reminder_text])
    add_parsed2 = parse_args(['add', '-n', 'Z'+filename, 'Z'+reminder_text])
    run_args(add_parsed)
    run_args(add_parsed2)

    # Test by index
    run_args(parse_args(['show', '0']))
    out, err = capsys.readouterr()
    assert out == 'A' + reminder_text + '\n'

    run_args(parse_args(['show', '1']))
    out, err = capsys.readouterr()
    assert out == 'Z' + reminder_text + '\n'

    # Test by filename
    run_args(parse_args(['show', add_parsed.fpath.name]))
    out, err = capsys.readouterr()
    assert out == 'A' + reminder_text + '\n'

    run_args(parse_args(['show', add_parsed2.fpath.name]))
    out, err = capsys.readouterr()
    assert out == 'Z' + reminder_text + '\n'

    # Test by filename minus extension
    name1, ext1 = get_parts(add_parsed.fpath.name)
    run_args(parse_args(['show', name1]))
    out, err = capsys.readouterr()
    assert out == 'A' + reminder_text + '\n'

    name2, ext2 = get_parts(add_parsed2.fpath.name)
    run_args(parse_args(['show', name2]))
    out, err = capsys.readouterr()
    assert out == 'Z' + reminder_text + '\n'


@given(reminder_text=text(alphabet=string.printable, min_size=1).filter(lambda x: x.isprintable()))
def test_list_not_long(capsys, move_reminders, reminder_text):
    """Make sure that list never prints too long a line."""
    assume(not reminder_text.startswith('-'))
    note(reminder_text)
    clean_reminders()
    len_space = 2
    len_index = 1
    len_filename = 10
    len_file_extension = 4
    len_reminder = 20

    len_line = len_index + len_space + len_filename + len_file_extension + len_space + len_reminder

    run_args(parse_args(['add', reminder_text]))

    run_args(parse_args(['ls']))
    out, err = capsys.readouterr()
    note(out)
    for line in out.split('\n'):
        assert len(line) <= len_line
 

def test_show_index_out_of_bounds(move_reminders):
    """Requesting by index when too large should raise an error."""
    clean_reminders()
    with raises(ValueError) as error:
        run_args(parse_args(['show', '0'], parser_class=ErrorRaisingArgumentParser))
    assert "List index out of range" in str(error)

    run_args(parse_args(['add', 'reminder']))
    run_args(parse_args(['show', '0'], parser_class=ErrorRaisingArgumentParser))
    with raises(ValueError) as error2:
        run_args(parse_args(['show', '1'], parser_class=ErrorRaisingArgumentParser))
    assert "List index out of range" in str(error2)

def test_not_reminder_exists(capsys, move_reminders):
    """Requesting a nonexistant reminder should raise an error."""
    clean_reminders()
    with raises(ValueError) as error:
        run_args(parse_args(['show', 'reminder'], parser_class=ErrorRaisingArgumentParser))
    assert "is not a reminder" in str(error)


@given(fname=text(alphabet=string.printable, min_size=1).filter(lambda x: is_valid_filename(x)))
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

    wrong = False
    if not is_valid_filename(filename):
        wrong = True
        with raises(ValueError):
            parse_args(['add', '-n', filename, "The Reminder Text"],
                       parser_class=ErrorRaisingArgumentParser)
        return

    if not wrong:
        with TemporaryDirectory() as tmpdirname:
            path = tmpdirname / Path(filename)
            path.touch()
            path.unlink()

@given(text(alphabet=string.ascii_letters+string.whitespace+string.digits, min_size=1).filter(is_valid_filename))
def test_whitespace_in_reminder(reminder_text):
    """Test that a reminder can contain whitespace."""
    parsed = parse_args(['add', reminder_text])
    assert parsed.reminder == reminder_text

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
                  (lambda s: not all([c in string.printable for c in s]), "printable")]

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

        with TemporaryDirectory() as tmpdirname:
            note(f"Namespace: {parsed}")
            note(f"Hasattr: {getattr(parsed, 'fpath')}")
            note(f"Path: {parsed.fpath}")
            path = tmpdirname / Path(parsed.fpath)
            assert is_valid_filename(parsed.fpath.name)
            path.touch()
            path.unlink()
