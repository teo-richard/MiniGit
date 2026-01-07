"""
MiniGit - A simple version control system
Entry point for the MiniGit CLI application.
"""

from commands import main_commands, history_commands, basic_commands, branch_commands
import argparse


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
    remove_parser = subparsers.add_parser("remove", help = "Add to staging area to be removed from repository.")
    add_parser.add_argument("files", nargs = "+", help = "Files to add to be comitted")
    remove_parser.add_argument("files", nargs = "+", help = "Files to add to be removed")

    # Empty staging area command
    empty_parser = subparsers.add_parser("empty", help = "Empty staging area")

    # Commit command
    commit_parser = subparsers.add_parser("commit", help = "Commit the staging area")
    commit_parser.add_argument("message", type = str, help = "Commit message")
    commit_parser.add_argument("-a", "--amend", action="store_true", help = "Change commit message of most recent commit")

    # Status command
    status_parser = subparsers.add_parser("status", help = "Get status")

    # Log command
    log_parser = subparsers.add_parser("log", help = "Print a log of commits in this branch.")

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
    branch_parser.add_argument("-d", "--delete", action = "store_true", help = "Delete branch")
    branch_parser.add_argument("branch", nargs = "?", default = None, help = "Branch to be removed")

    # Merge command
    merge_parser = subparsers.add_parser("merge", help = "Merge branches")
    merge_parser.add_argument("branch", help = "Branch to be merged into current branch")
    merge_parser.add_argument("-m", "--message", type = str, default = "Merge commit", help = "Merge commit message")

    # Parse command-line arguments
    args = parser.parse_args()

    # Route to appropriate command handler
    if args.command == "init":
        main_commands.create_minigit()

    if args.command == "add":
        main_commands.stage(args.files, "additions")

    if args.command == "remove":
        main_commands.stage(args.files, "removals")

    if args.command == "empty":
        basic_commands.empty()
        print("\nStaging area emptied.\n")

    if args.command == "commit":
        commit_message = args.message
        main_commands.commit(commit_message)
        basic_commands.empty()

    if args.command == "status":
        history_commands.status()

    if args.command == "log":
        history_commands.log()

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
        if args.delete == True:
            branch_name = args.branch
            branch_commands.branch_delete(branch_name = branch_name)
        else:
            branch_commands.branch_list()

    if args.command == "merge":
        branch_name = args.branch
        merge_message = args.message
        branch_commands.merge(merge_branch_name = branch_name, message = merge_message)


    


if __name__ == "__main__":
    main()

