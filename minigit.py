"""
MiniGit - A simple version control system
Entry point for the MiniGit CLI application.
"""

from commands import main_commands, info_commands, basic_commands, branch_commands, history_commands, remote_commands
import argparse
import utils
from utils import CommitNotFoundError

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
    empty_parser.add_argument("filename", nargs = "+", help = "File to take out of staging area")

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
    remote_parser.add_argument("add", action ="store_true", help = "add remote repo")
    remote_parser.add_argument("path", nargs=1, help = "Path to remote repo")

    # Push command to push to a remote repo
    push_parser = subparsers.add_parser("push")
    push_parser.add_argument("name")
    push_parser.add_argument("branch")

    # Parse command-line arguments
    args = parser.parse_args()

    # If necessary, check if commit is valid
    if args.command in ("revert", "reset", "checkout"):
        try:
            utils.get_commit(args.hash)
        except CommitNotFoundError as e:
            print(e)
            return

    # Route to appropriate command handler
    if args.command == "init":
        main_commands.init()

    if args.command == "add":
        main_commands.stage(args.files, "additions")

    if args.command == "remove":
        main_commands.stage(args.files, "removals")

    if args.command == "empty":
        filename = args.filename
        if args.file:
            basic_commands.empty_file(filename)
        else:
            basic_commands.empty()
            print("\nStaging area emptied.\n")

    if args.command == "commit":
        message = args.message
        if args.amend:
            info_commands.amend(message)
        else:
            main_commands.commit(message)
            basic_commands.empty()
            print("\nStaging area has been emptied. Congratulations on your commit!\n")

    if args.command == "status":
        info_commands.status()

    if args.command == "log":
        if args.all:
            info_commands.log_all()
        else:
            info_commands.log()

    if args.command == "checkout":
        hash = args.hash
        branch_commands.checkout_commit(checkout_hash = hash)

    if args.command == "switch":
        branch_name = args.branch
        if args.create == True:
            branch_commands.branch_create(branch_name = branch_name)
        else:
            branch_commands.branch_switch(branch_name = branch_name)
        
    if args.command == "branch":
        if args.delete:
            branch_commands.branch_delete(args.branch)
        else:
            branch_commands.branch_list()

    if args.command == "merge":
        branch_name = args.branch
        merge_message = args.message
        branch_commands.merge(merge_branch_name = branch_name, message = merge_message)

    if args.command == "minigitignore":
        files = args.files
        basic_commands.mgignore(files)

    if args.command == "revert":
        hash = args.hash
        message = args.message
        history_commands.revert(hash, message)

    if args.command == "reset":
        hash = args.hash
        if args.hard:
            history_commands.reset(hash, "hard")
        elif args.soft:
            history_commands.reset(hash, "soft")
        else:
            print("Specify a flaggy mc flag flag \"--hard\" or \"--soft\" please!")

    if args.command == "reflog":
        info_commands.reflog()

    if args.command == "remote":
        if args.add:
            main_commands.init(args.path)
        else:
            print("dummy")

    if args.command == "push":
        ancestors_to_push, path_to_repo, path_to_remote_branch = remote_commands.remote_prep_push(args.name, args.branch)
        remote_commands.remote_push(ancestors_to_push, path_to_repo, path_to_remote_branch)


if __name__ == "__main__":
    main()

