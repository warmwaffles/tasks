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
  * `#project` - Make a task apart of a project or multiple projects.
  * `@completed(DATE)` - Mark a task as completed.
  * `@critical` - Mark a task as critical.
  * `@important` - Mark a task as important.
  * `@high` - Mark a task as high priority.
  * `@low` - Mark a task as low priority.
  * `@due(DATE)` - Mark a task as due on a specific date.

## Requirements

* `ripgrep`
* `sed`
* `perl`
* `date` (GNU flavor for now)

## Installing

Just copy the `tasks` script somewhere on your path.

## Adding Tasks

```sh
tasks add "+feature ability to add new #tasks"
```

```sh
tasks add -c "finished basic readme +example for #tasks"
```

## Listing Tasks

```sh
tasks ls
```

## Get Summary For The Day

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
