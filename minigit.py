#!/usr/bin/env python3

"""
MiniGit - A simple version control system
Entry point for the MiniGit CLI application.
"""

from commands import main_commands, info_commands, basic_commands, branch_commands, history_commands, remote_commands
import argparse
import utils
from utils import CommitNotFoundError
import subprocess
import os

VOICE_RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "voice_recordings")

def speak(command):
       path = f"VOICE_RECORDINGS_DIR/minigit_{command}.m4a"
       if os.path.exists(path):
           subprocess.run(["afplay", path])


def _handle_empty(args):
        if args.file:
            basic_commands.empty_file(args.filename)
        else:
            basic_commands.empty()
            print("\nStaging area emptied.\n")

def _handle_commit(args):
    if args.amend:
        info_commands.amend(args.message)
    else:
        main_commands.commit(args.message)
        basic_commands.empty()
        print("\nStaging area has been emptied. Congratulations on your commit!\n")

def _handle_log(args):
    if args.all:
        info_commands.log_all()
    else:
        info_commands.log()

def _handle_switch(args):
        branch_name = args.branch
        if args.create == True:
            branch_commands.branch_create(branch_name = branch_name)
        else:
            branch_commands.branch_switch(branch_name = branch_name)



def _handle_branch(args):
        if args.delete:
            branch_commands.branch_delete(args.branch)
        elif len(args.branch) == 0:
            branch_commands.branch_list()
        else:
            print("Command not recognized. Did you mean --delete?")

def _handle_reset(args):
    if args.hard:
        history_commands.reset(args.hash, "hard")
    elif args.soft:
        history_commands.reset(args.hash, "soft")
    else:
        print("Specify a flaggy mc flag flag \"--hard\" or \"--soft\" please!")



def _handle_push(args):
    try:
        ancestors_to_push, path_to_repo, path_to_remote_branch = remote_commands.remote_prep_push(args.name, args.branch)
        remote_commands.remote_push(ancestors_to_push, path_to_repo, path_to_remote_branch)
    except TypeError:
        print("Your remote branch is already up to date.")



def main():
    """
    Main entry point for MiniGit CLI.

    Sets up argument parsing and routes commands to their respective handlers:
    - init: Initialize a new repository
    - add: Stage files for commit
    - remove: Mark files for removal
    - empty: Clear the staging area
    - commit: Create a new commit
    - status: Show repository status
    - log: Display commit history
    - checkout: Switch to a specific commit
    """
    # Set up the main argument parser
    parser = argparse.ArgumentParser(description="MiniGit main function")
    subparsers = parser.add_subparsers(dest="command")

    # Initialize repository command
    init_parser = subparsers.add_parser("init", help = "Initialize Project")

    # Add files to staging area command
    add_parser = subparsers.add_parser("add", help = "Add to staging area to be committe")
    add_parser.add_argument("files", nargs = "+", help = "Files to add to be comitted")
    remove_parser = subparsers.add_parser("remove", help = "Add to staging area to be removed from repository.")
    remove_parser.add_argument("files", nargs = "+", help = "Files to add to be removed")

    # Empty staging area command
    empty_parser = subparsers.add_parser("empty", help = "Empty staging area")
    empty_parser.add_argument("-f", "--file", action="store_true", help = "Take a file out of staging area")
    # Changed to accept multiple files using nargs="+" for selective unstaging
    empty_parser.add_argument("filename", nargs = "*", help = "File to take out of staging area")

    # Commit command
    commit_parser = subparsers.add_parser("commit", help = "Commit the staging area")
    commit_parser.add_argument("message", type = str, help = "Commit message")
    commit_parser.add_argument("-a", "--amend", action="store_true", help = "Change commit message of most recent commit")

    # Status command
    status_parser = subparsers.add_parser("status", help = "Get status")

    # Log command
    log_parser = subparsers.add_parser("log", help = "Print a log of commits in this branch.")
    log_parser.add_argument("--all", action="store_true", help = "Log of all commits accessible from branches")

    # Checkout command
    checkout_parser = subparsers.add_parser("checkout", help = "Check out a commit")
    checkout_parser.add_argument("hash", type = str, help = "The commit hash")

    # Branch switch/branch checkout command
    switch_parser = subparsers.add_parser("switch", help = "Switch branches")
    switch_parser.add_argument("branch", type = str, help = "The branch")
    switch_parser.add_argument("-c", "--create", action = "store_true", 
                          help = "Create the branch if it does not exist")
    
    # Branch list and delete commands
    branch_parser = subparsers.add_parser("branch", help = "List branches")
    branch_parser.add_argument("-d", "--delete", action = "store_true", help = "Remove reference to branch")
    branch_parser.add_argument("branch", nargs = "*", default = None, help = "Branch to be removed")

    # Merge command
    merge_parser = subparsers.add_parser("merge", help = "Merge branches")
    merge_parser.add_argument("branch", help = "Branch to be merged into current branch")
    merge_parser.add_argument("-m", "--message", type = str, default = "Merge commit", help = "Merge commit message")

    # minigitignore command
    mgignore_parser = subparsers.add_parser("minigitignore", help = "Add a file to minigitignore")
    mgignore_parser.add_argument("files", nargs = "+", help = "Files to add to the minigitignore")

    # Revert command
    revert_parser = subparsers.add_parser("revert", help = "Revert to earlier commit. ")
    revert_parser.add_argument("hash", help = "The commit to revert to.")
    revert_parser.add_argument("-m", "--message", type = str, default = None, help = "Revert commit message.")

    # Reset command
    reset_parser = subparsers.add_parser("reset", help = "Reset to earlier commit. Destroys history.")
    reset_parser.add_argument("--hard", action = "store_true", help = "Hard reset")
    reset_parser.add_argument("--soft", action = "store_true", help = "soft reset")
    reset_parser.add_argument("hash", help = "The commit to reset to.")

    # Reflog command
    reflog_parser = subparsers.add_parser("reflog", help = "List ALLLLLL your commits EVERRRRR.")

    # Remote add command to add a remote repo
    remote_parser = subparsers.add_parser("remote", help = "Remote")
    remote_parser.add_argument("name", help = "Name of remote repo e.g. origin")
    remote_parser.add_argument("path", help = "Path to remote repo")

    # Push command to push to a remote repo
    push_parser = subparsers.add_parser("push")
    push_parser.add_argument("name")
    push_parser.add_argument("branch")

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help = "fetch from a remote repo yk wazzup my g")
    fetch_parser.add_argument("name")
    fetch_parser.add_argument("branch")

    # Pull command
    pull_parser = subparsers.add_parser("pull", help = "pull deez nuts out yo face")
    pull_parser.add_argument("name")
    pull_parser.add_argument("branch")


    # Parse command-line arguments
    args = parser.parse_args()

    # If necessary, check if commit is valid
    if args.command in ("revert", "reset", "checkout"):
        try:
            utils.get_commit(args.hash)
        except CommitNotFoundError as e:
            if args.command == "checkout":
                branch_commands.checkout_branch_instead_of_commit(args.hash, e)
            else:
                print(e)
            return
        
    dispatch = {
        "init": lambda args: main_commands.init(),
        "add": lambda args: main_commands.stage(args.files, "additions"),
        "remove": lambda args: main_commands.stage(args.files, "removals"),
        "empty": _handle_empty,
        "commit": _handle_commit,
        "status": lambda args: info_commands.status_general(),
        "log": _handle_log,
        "checkout": lambda args: branch_commands.checkout_commit(checkout_hash = args.hash),
        "switch": _handle_switch,
        "branch": _handle_branch,
        "merge": lambda args: branch_commands.merge(merge_branch_name=args.branch, message=args.message),
        "minigitignore": lambda args: basic_commands.mgignore(args.files),
        "revert": lambda args: history_commands.revert(args.hash, args.message),
        "reset": _handle_reset,
        "reflog": lambda args: info_commands.reflog(),
        "remote": lambda args: remote_commands.remote_add(args.name, args.path),
        "push": _handle_push,
        "fetch": lambda args: remote_commands.fetch(args.name, args.branch),
        "pull": lambda args: remote_commands.pull(args.name, args.branch)
    }

    if args.command in dispatch:
        speak(args.command)
        dispatch[args.command](args)



if __name__ == "__main__":
    main()
