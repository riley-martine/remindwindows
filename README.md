# Remind Windows

This is a python program for making reminders. Reminders stay on the screen as seperate windows. They can be snoozed for later or deleted. If the windows are closed (on purpose or because of shutdown) they will be re-created on program start. 

The process runs as a daemon. If no reminders are active, the program halts.


## Installation
Make sure you have the lockfile, daemon, PyQt5, and watchdog libraries installed, as well as python3. (Tested with python3.6)

The rest of this section is `//TODO`. It will show how to make the daemon process start at launch.

## Usage
Right now, reminders are managed by creating, deleting, and editing files in the `~/.remindwindows/` directory. Reminder files are required to end with `.rem`. The name of the file is not important. The content of the file is the reminder text.

Launch the program by running the `remindwindows/remindme.py` file.


## Todo
  [ ] Write tests
  [ ] Add test coverage
  [ ] Segment out daemon, logic, and GUI
  [ ] Add cli interface
  [ ] Make package
