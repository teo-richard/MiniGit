import sys
from commands import main_commands
from commands import history_commands
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

    comit_parser = subparsers.add_parser("commit", help = "Commit the staging area")

    status_parser = subparsers.add_parser("status", help = "Get status")

    args = parser.parse_args()

    if args.command == "init":
        main_commands.create_minigit()
    
    if args.command == "add":
        main_commands.stage(args.files, "additions")

    if args.command == "remove":
        main_commands.stage(args.files, "removals")
    
    if args.command == "empty":
        main_commands.empty()
        print("Staging area emptied. ")

    if args.command == "commit":
        main_commands.commit()

    if args.command == "status":
        history_commands.status()


    


if __name__ == "__main__":
    main()

