import sys
from commands import main_commands
from commands import history_commands
from commands import basic_commands
import argparse



def main():
    parser = argparse.ArgumentParser(description="MiniGit main function")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help = "Initialize Project")

    add_parser = subparsers.add_parser("add", help = "Add to staging area to be committe")
    remove_parser = subparsers.add_parser("remove", help = "Add to staging area to be removed from repository.")
    add_parser.add_argument("files", nargs = "+", help = "Files to add to be comitted")
    remove_parser.add_argument("files", nargs = "+", help = "Files to add to be removed")

    empty_parser = subparsers.add_parser("empty", help = "Empty staging area")

    commit_parser = subparsers.add_parser("commit", help = "Commit the staging area")
    commit_parser.add_argument("message", type = str, help = "Commit message")

    status_parser = subparsers.add_parser("status", help = "Get status")
    log_parser = subparsers.add_parser("log", help = "Print a log of commits in this branch.")

    args = parser.parse_args()

    if args.command == "init":
        main_commands.create_minigit()
    
    if args.command == "add":
        main_commands.stage(args.files, "additions")

    if args.command == "remove":
        main_commands.stage(args.files, "removals")
    
    if args.command == "empty":
        basic_commands.empty()
        print("Staging area emptied. ")

    if args.command == "commit":
        commit_message = args.message
        main_commands.commit(commit_message)

    if args.command == "status":
        history_commands.status()
    
    if args.command == "log":
        history_commands.log()


    


if __name__ == "__main__":
    main()

