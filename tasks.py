#!/usr/bin/env python

from __future__ import print_function
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import mkstemp
import argparse
import enum
import os
import os.path
import re
import shutil
import sys


# Get the tasks directory that we are going to use
if os.environ.get("TASKS_PATH"):
    TASKS_PATH = os.environ["TASKS_PATH"]
else:
    TASKS_PATH = Path.home().joinpath(".tasks")

SQUEEZE_REGEX = re.compile(r"\s+")
TASK_REGEX = re.compile(r"(\d+)\s+-\s+\[(.)\]\s+-\s+(.*)")
TAGS_REGEX = re.compile(r"\+([\w\-\_]+)")
DIRECTIVES_REGEX = re.compile(r"@([\w\(\)\-\_\s\:]+)")
DIRECTIVE_NAMES_REGEX = re.compile(r"(\w+)(.*)?")
DIRECTIVE_PARAMS_REGEX = re.compile(r"([^()]+\((.*)\))")
HIGH_PRIORITY_REGEX = re.compile(r"@high")
MEDIUM_PRIORITY_REGEX = re.compile(r"@medium")
LOW_PRIORITY_REGEX = re.compile(r"@low")
PRIORITY_REGEX = re.compile(f"@(low|medium|high)")
BLOCKED_REGEX = re.compile(r"@blocked")
DELAYED_REGEX = re.compile(r"@delayed")
COMPLETED_REGEX = re.compile(r"(@completed\(.*\))")
CANCELLED_REGEX = re.compile(r"(@cancelled\(.*\))")
DUE_REGEX = re.compile(r"(@due\(.*\))")
DAY_REGEX = re.compile(r"(\d+)d")
DEFAULT_CONTEXT = "default"


def printerr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def parse_datetime(string):
    return datetime.strptime(string, "%Y-%m-%d %H:%M")


def parse_due(string):
    if string == "today" or string == "now":
        return datetime.now()
    if string == "tomorrow":
        return datetime.now() + timedelta(days=1)

    matched = DAY_REGEX.findall(string)
    if matched:
        return datetime.now() + timedelta(days=int(matched[0]))

    return parse_datetime(string)


def completed_yesterday(task):
    if not task.completed:
        return False

    now = datetime.now()
    return task.completed + timedelta(hours=28) >= now


def completed_today(task):
    if not task.completed:
        return False
    now = datetime.now()
    return (
        task.completed < (now + timedelta(hours=12)) and
        task.completed > (now - timedelta(hours=12))
    )


def incomplete(task):
    return task.state == TaskState.INCOMPLETED


def not_delayed(task):
    return not task.delayed


class Colors:
    OFF = '\033[00m'
    BLACK = '\033[0;30m'
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[0;37m'

    BLACK_BOLD = '\033[1;30m'
    RED_BOLD = '\033[1;31m'
    GREEN_BOLD = '\033[1;32m'
    YELLOW_BOLD = '\033[1;33m'
    BLUE_BOLD = '\033[1;34m'
    PURPLE_BOLD = '\033[1;35m'
    CYAN_BOLD = '\033[1;36m'
    WHITE_BOLD = '\033[1;37m'

    BLACK_BG = '\033[40m'
    RED_BG = '\033[41m'
    GREEN_BG = '\033[42m'
    YELLOW_BG = '\033[43m'
    BLUE_BG = '\033[44m'
    PURPLE_BG = '\033[45m'
    CYAN_BG = '\033[46m'
    GRAY_BG = '\033[47m'


class ConcatAction(argparse.Action):
    """
    Takes an argument and concats the strings into one string
    """
    def __init__(self, option_strings, dest, **kwargs):
        super(ConcatAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        values = " ".join(list(values))
        setattr(namespace, self.dest, values)


class TaskState(enum.Enum):
    COMPLETED = "x"
    INCOMPLETED = " "
    CANCELLED = "-"

    @classmethod
    def parse(cls, value):
        if value == cls.CANCELLED.value:
            return cls.CANCELLED
        if value == cls.COMPLETED.value:
            return cls.COMPLETED
        return cls.INCOMPLETED


class Priority(enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Task:
    def __init__(
        self,
        id,
        message=None,
        state=None,
        tags=None,
        due=None,
        priority=None,
        completed=None,
        blocked=None,
        delayed=None
    ):
        self.id = id
        self.message = message
        self.due = due
        self.priority = priority
        self.completed = completed
        self.blocked = blocked
        self.delayed = delayed
        if tags:
            self.tags = tags
        else:
            self.tags = []

        if state:
            self.state = state
        else:
            self.state = TaskState.INCOMPLETED

    def __repr__(self):
        return f"Task({vars(self)})"

    def _strip_state(self):
        self.message = COMPLETED_REGEX.sub("", self.message)
        self.message = CANCELLED_REGEX.sub("", self.message)
        self.message = self.message.rstrip()
        self.message = SQUEEZE_REGEX.sub(" ", self.message)

    def _strip_blocked(self):
        self.message = BLOCKED_REGEX.sub("", self.message)
        self.message = self.message.rstrip()

    def _strip_delayed(self):
        self.message = DELAYED_REGEX.sub("", self.message)
        self.message = self.message.rstrip()

    def _replace_due(self):
        ts = self.due.isoformat(sep=" ", timespec="minutes")
        self.message = DUE_REGEX.sub(f"@due({ts})", self.message)

    def set_priority(self, level):
        if level == "low" or level == "l" or level == "1":
            level = "low"
            self.priority = Priority.LOW
        elif level == "medium" or level =="m" or level == "2":
            level = "medium"
            self.priority = Priority.MEDIUM
        elif level == "high" or level == "h" or level == "3":
            level = "high"
            self.priority = Priority.HIGH
        elif level == "none" or level == "n" or level == "0":
            self.priority = None
            self.message = PRIORITY_REGEX.sub("", self.message)
            return
        else:
            return

        if PRIORITY_REGEX.search(self.message):
            self.message = PRIORITY_REGEX.sub(f"@{level}", self.message)
        else:
            self.message += f" @{level}"

    def delay(self):
        self.delayed = True
        self._strip_delayed()
        self.message += " @delayed"

    def undelay(self):
        self.delayed = False
        self._strip_delayed()

    def block(self):
        self.blocked = True
        self._strip_blocked()
        self.message += " @blocked"

    def unblock(self):
        self.blocked = False
        self._strip_blocked()

    def complete(self):
        self.state = TaskState.COMPLETED
        self._strip_state()
        now = datetime.now().isoformat(sep=" ", timespec="minutes")
        self.message += f" @completed({now})"

    def uncomplete(self):
        self.state = TaskState.INCOMPLETED
        self._strip_state()

    def cancel(self):
        self.state = TaskState.CANCELLED
        self._strip_state()
        now = datetime.now().isoformat(sep=" ", timespec="minutes")
        self.message += f" @cancelled({now})"

    def formatted_message(self):
        message = self.message

        # color up the tags
        message = TAGS_REGEX.sub(f"{Colors.GREEN}+\\1{Colors.OFF}", message)

        # color up priorities
        message = HIGH_PRIORITY_REGEX.sub(
            f"{Colors.WHITE_BOLD}{Colors.RED_BG}@high{Colors.OFF}",
            message
        )
        message = MEDIUM_PRIORITY_REGEX.sub(
            f"{Colors.YELLOW_BOLD}@medium{Colors.OFF}",
            message
        )
        message = LOW_PRIORITY_REGEX.sub(
            f"{Colors.WHITE_BOLD}@low{Colors.OFF}",
            message
        )

        # color up completion
        message = COMPLETED_REGEX.sub(
            f"{Colors.GREEN_BOLD}\\1{Colors.OFF}",
            message
        )
        message = CANCELLED_REGEX.sub(
            f"{Colors.PURPLE_BOLD}\\1{Colors.OFF}",
            message
        )

        # color up due
        message = DUE_REGEX.sub(
            f"{Colors.CYAN_BOLD}\\1{Colors.OFF}",
            message
        )

        # color up blocked
        message = BLOCKED_REGEX.sub(
            f"{Colors.WHITE_BOLD}{Colors.RED_BG}@blocked{Colors.OFF}",
            message
        )

        # color delayed
        message = DELAYED_REGEX.sub(
            f"{Colors.WHITE_BOLD}@delayed{Colors.OFF}",
            message
        )

        return message

    def standup(self):
        if self.state == TaskState.COMPLETED:
            return f"  ● {self.formatted_message()}"
        if self.state == TaskState.CANCELLED:
            return f"  ⊝ {self.formatted_message()}"
        return f"  ○ {self.formatted_message()}"

    def to_s(self, formatted=True):
        if formatted:
            return f"{self.id} - [{self.state.value}] - {self.formatted_message()}"
        return f"{self.id} - [{self.state.value}] - {self.message}"

    def apply(self, message):
        self.message = message
        self.tags = TAGS_REGEX.findall(message)

        for d in DIRECTIVES_REGEX.findall(message):
            name = DIRECTIVE_NAMES_REGEX.findall(d)[0][0]
            parts = DIRECTIVE_PARAMS_REGEX.findall(d)
            if parts:
                parts = parts[0]

            if name == "high":
                self.priority = Priority.HIGH
            elif name == "medium":
                self.priority = Priority.MEDIUM
            elif name == "low":
                self.priority = Priority.LOW
            elif name == "completed":
                self.state = TaskState.COMPLETED
                if parts:
                    self.completed = parse_datetime(parts[1])
            elif name == "due":
                if parts:
                    self.due = parse_due(parts[1])
                    self._replace_due()
            elif name == "blocked":
                self.blocked = True
            elif name == "delayed":
                self.delayed = True

        return self

    @classmethod
    def parse(cls, line):
        groups = TASK_REGEX.match(line)
        id = int(groups.group(1))
        state = TaskState.parse(groups.group(2))
        message = groups.group(3)

        return cls(id=id, state=state).apply(message)

    @classmethod
    def new(cls, id, message, state):
        return cls(id=id, state=state).apply(message)


class TasksRepo:
    def __init__(self, path):
        self.path = path
        self.tasks = {}
        for line in path.read_text().split("\n"):
            if line:
                task = Task.parse(line)
                self.tasks[task.id] = task

    def find(self, id):
        return self.tasks.get(id)

    def all(self):
        return self.tasks.values()

    def insert(self, task):
        self.tasks[task.id] = task
        self._flush()

    def update(self, task):
        self.tasks[task.id] = task
        self._flush()

    def remove(self, task):
        del self.tasks[task.id]
        self._flush()

    def _flush(self):
        """
        We will take all of the tasks we have, write them to a temporary file,
        and then move them to replace the old file
        """
        fh, abs_path = mkstemp()

        with os.fdopen(fh, 'w') as temp:
            for task in self.all():
                temp.write(task.to_s(formatted=False))
                temp.write("\n")
        os.remove(self.path)
        shutil.move(abs_path, self.path)


class TaskManager:
    def __init__(self, directory, task_id=None, organization=None):
        self.directory = Path(directory)
        if task_id:
            self.task_id = task_id
        else:
            self.task_id = 1

        if organization:
            self.organization = organization
        else:
            self.organization = "default"

        self._current = None
        self._archive = None

    def __repr__(self):
        return f"TaskManager({vars(self)})"

    @property
    def current(self):
        if not self._current:
            self._current = TasksRepo(self.current_log_path)
        return self._current

    @property
    def archive(self):
        if not self._archive:
            self._archive = TasksRepo(self.archive_log_path)
        return self._archive

    def _setup_context(self):
        context_path = self.directory.joinpath("context")

        if context_path.exists():
            text = context_path.read_text()
            parts = text.split("\n", 1)
            if len(parts) >= 1:
                self.organization = parts[0]

            if not self.organization:
                context_path.write_text(self.organization)
        else:
            context_path.write_text(self.organization)

    @property
    def organization_path(self):
        return self.directory.joinpath(self.organization)

    @property
    def archive_log_path(self):
        return self.directory.joinpath(self.organization, "archive.log")

    @property
    def current_log_path(self):
        return self.directory.joinpath(self.organization, "current.log")

    @property
    def task_id_path(self):
        return self.directory.joinpath(self.organization, "taskid")

    def _increment_task_id(self):
        self.task_id += 1
        self.task_id_path.write_text(str(self.task_id))

    def _setup_organization(self):
        if not self.organization_path.exists():
            self.organization_path.mkdir()

        if not self.archive_log_path.exists():
            self.archive_log_path.touch()

        if not self.current_log_path.exists():
            self.current_log_path.touch()

        if self.task_id_path.exists():
            text = self.task_id_path.read_text()
            parts = text.split("\n", 1)
            if parts:
                self.task_id = int(parts[0])
        else:
            self.task_id_path.write_text(str(self.task_id))

    def setup(self):
        self.directory.mkdir(exist_ok=True)
        self._setup_context()
        self._setup_organization()

    def add_task(self, args):
        completed = args.complete
        message = args.message
        id = self.task_id + 1
        state = None

        if completed:
            state = TaskState.COMPLETED

        task = Task.new(id=id, message=message, state=state)
        self.current.insert(task)
        self._increment_task_id()

    def edit_task(self, args):
        message = args.message
        task_id = args.task_id

        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")

        task.apply(message)
        self.current.update(task)

    def list_tasks(self, args):
        tasks = self.current.all()
        for task in tasks:
            print(task.to_s())

    def uncomplete_task(self, args):
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        task.uncomplete()
        self.current.update(task)

    def complete_task(self, args):
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        task.complete()
        self.current.update(task)

    def cancel_task(self, args):
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        task.cancel()
        self.current.update(task)

    def remove_task(self, args):
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        self.current.remove(task)

    def summary_standup(self, args):
        tasks = self.current.all()

        print("*Yesterday*")
        for task in filter(completed_yesterday, tasks):
            print(task.standup())

        print()
        print("*Today*")
        for task in filter(completed_today, tasks):
            print(task.standup())

        for task in filter(not_delayed, filter(incomplete, tasks)):
            print(task.standup())


    def summary(self, args):
        self.summary_standup(args)

    def switch_context(self, args):
        context_path = self.directory.joinpath("context")

        organization = args.organization
        self.organization = organization
        context_path.write_text(self.organization)
        self._setup_organization()

    def archive_task(self, args):
        ...

    def clean_tasks(self, args):
        ...

    def block_task(self, args):
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        task.block()
        self.current.update(task)

    def unblock_task(self, args):
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        task.unblock()
        self.current.update(task)

    def set_priority(self, args):
        priority = args.priority
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        task.set_priority(priority)
        self.current.update(task)

    def delay_task(self, args):
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        task.delay()
        self.current.update(task)

    def undelay_task(self, args):
        task_id = args.task_id
        task = self.current.find(task_id)
        if not task:
            printerr(f"Task({task_id}) not found")
            return
        task.undelay()
        self.current.update(task)


manager = TaskManager(TASKS_PATH)
manager.setup()


COMMANDS = {}

parser = argparse.ArgumentParser(
    prog="tasks",
    description="A task list manager",
    epilog="""
    Set TASKS_HOME to change where the current set of tasks are stored.
    """
)
subparser = parser.add_subparsers(title="subcommands", dest="command")

# #############################################################################
# ADDING
add_parser = subparser.add_parser(
    "add",
    help="add a new task",
    aliases=["a"]
)
add_parser.add_argument(
    "-c",
    "--complete",
    help="mark task as completed",
    action="store_true"
)
add_parser.add_argument(
    "message",
    type=str,
    nargs="+",
    help="the actual task you want to do",
    action=ConcatAction
)

COMMANDS["a"] = manager.add_task
COMMANDS["add"] = manager.add_task


# #############################################################################
# ARCHIVING
archive_parser = subparser.add_parser(
    "archive",
    help="move a task to the archive"
)
COMMANDS["archive"] = manager.archive_task

# #############################################################################
# CLEANING
clean_parser = subparser.add_parser(
    "clean",
    help="removes completed tasks into the archive"
)
COMMANDS["clean"] = manager.clean_tasks


# #############################################################################
# COMPLETING
complete_parser = subparser.add_parser(
    "complete",
    help="mark a task as completed",
    aliases=["c"]
)
complete_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
COMMANDS["complete"] = manager.complete_task
COMMANDS["c"] = manager.complete_task

# #############################################################################
# COMPLETING
cancel_parser = subparser.add_parser(
    "cancel",
    help="mark a task as cancelled"
)
cancel_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
COMMANDS["cancel"] = manager.cancel_task

# #############################################################################
# EDITING
edit_parser = subparser.add_parser(
    "edit",
    help="edit a specific task",
    aliases=["e"]
)
edit_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
edit_parser.add_argument(
    "message",
    type=str,
    nargs="+",
    help="the actual task you want to do",
    action=ConcatAction
)
COMMANDS["edit"] = manager.edit_task
COMMANDS["e"] = manager.edit_task

# #############################################################################
# LISTING
list_parser = subparser.add_parser(
    "list",
    help="list tasks",
    aliases=["ls"]
)
COMMANDS["list"] = manager.list_tasks
COMMANDS["ls"] = manager.list_tasks

# #############################################################################
# REMOVING
remove_parser = subparser.add_parser(
    "remove",
    help="remove a task",
    aliases=["rm"]
)
remove_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
COMMANDS["remove"] = manager.remove_task
COMMANDS["rm"] = manager.remove_task

# #############################################################################
# SUMMARY
summary_parser = subparser.add_parser(
    "summary",
    help="get a summary of tasks",
    aliases=["s"]
)
COMMANDS["summary"] = manager.summary
COMMANDS["s"] = manager.summary

# #############################################################################
# UNCOMPLETING
uncomplete_parser = subparser.add_parser(
    "uncomplete",
    help="uncomplete a task",
    aliases=["C", "u"]
)
uncomplete_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
COMMANDS["uncomplete"] = manager.uncomplete_task
COMMANDS["u"] = manager.uncomplete_task
COMMANDS["C"] = manager.uncomplete_task


# #############################################################################
# USING
use_parser = subparser.add_parser(
    "use",
    help="switch contexts to work in"
)
use_parser.add_argument(
    "organization",
    type=str,
    help="the origanization to change to"
)
COMMANDS["use"] = manager.switch_context

# #############################################################################
# Blocking
block_parser = subparser.add_parser(
    "block",
    help="block a task",
    aliases=["b"]
)
block_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
COMMANDS["block"] = manager.block_task
COMMANDS["b"] = manager.block_task

# #############################################################################
# Un-Blocking
unblock_parser = subparser.add_parser(
    "unblock",
    help="unblock a task",
    aliases=["B"]
)
unblock_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
COMMANDS["unblock"] = manager.unblock_task
COMMANDS["B"] = manager.unblock_task

# #############################################################################
# Priority
priority_parser = subparser.add_parser(
    "priority",
    help="set the priority level of a task",
    aliases=["p"]
)
priority_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
priority_parser.add_argument(
    "priority",
    type=str,
    help="the priority level"
)
COMMANDS["priority"] = manager.set_priority
COMMANDS["p"] = manager.set_priority

# #############################################################################
# Delayed
delay_parser = subparser.add_parser(
    "delay",
    help="tag a task as delayed",
    aliases=["d"]
)
delay_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
COMMANDS["delay"] = manager.delay_task
COMMANDS["d"] = manager.delay_task

# #############################################################################
# Undelay a task
undelay_parser = subparser.add_parser(
    "undelay",
    help="undelay a task",
    aliases=["D"]
)
undelay_parser.add_argument(
    "task_id",
    type=int,
    help="the id of the task"
)
COMMANDS["undelay"] = manager.undelay_task
COMMANDS["D"] = manager.undelay_task

#
# Now do the work
#

args = parser.parse_args()

if args.command is not None:
    COMMANDS[args.command](args)
else:
    parser.print_help()
