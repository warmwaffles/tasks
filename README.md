# Tasks

A basic bash script that helps you keep track of things you did.

All tasks are written to a flat file located underneath the `$TASKS_DIRECTORY`
environment variable. By default this is `$HOME/.tasks`.

It is recommended that you go into that directory and initialize the git
repository there and go into it every now and then and save the changes made to
the files. This is useful for reverting should you mess something up.

It is highly recommended that you run `--help` with all of the sub commands.

## Task Format

The formatting is fairly simple. The message is just plain text with some
markups added.

  * `+tag` - A tag for a task. Useful for adding some meta information about a
    task.
  * `@completed(DATE)` - Mark a task as completed.
  * `@cancelled(DATE)` - Mark a task as cancelled.
  * `@high` - Mark a task as high priority.
  * `@medium` - Mark a task as medium priority.
  * `@low` - Mark a task as low priority.
  * `@due(DATE)` - Mark a task as due on a specific date.

## Requirements

* python 3

## Installing

Copy the files somewhere on your path. Alternatively, clone the repo and add the
repo to your `$PATH`.

```sh
cp tasks.py ~/bin/tasks
```

or

```sh
git clone git@github.com:warmwaffles/tasks.git /usr/local/src/tasks
export PATH="/usr/local/src/tasks:$PATH"
```

## Switching Organizations

```sh
tasks use personal
```

```sh
tasks use simplecasual
```

All this does is set the tasks to be stored in sub directories in the
`TASKS_DIRECTORY` path. For instance:

```txt
.
├── context
├── personal
│   ├── current.log
│   ├── archived.log
│   └── taskid
└── simplecasual
    ├── current.log
    ├── archived.log
    └── taskid
```

## Adding Tasks

### Create a task todo

```sh
tasks add "+feature ability to add new #tasks"
```

### Mark a task as completed

```sh
tasks add -c "finished basic readme +example for #tasks"
```

### Specify an id for the task being added

Sometimes you need to reinsert a task that you deleted

```sh
tasks add --id 21 "+feature ability to list #tasks in order of priority"
```

## Listing Tasks

```sh
tasks ls
```

## Get Summary For The Day

```sh
tasks summary
```

## Get Summary For The Week

```sh
tasks summary --weekly
```

## Get Summary For A Specific Project

```sh
tasks summary -p someproject
```

## Remove Task

```sh
tasks remove 12
```

## Edit Task

Currently not supported. Is a work in progress still.

## Cleaning

```sh
tasks clean
```

## Archiving

```sh
tasks archive
```
