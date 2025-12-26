import sys
from commands import init

def main():
    command = sys.argv[1] # gitlet command

    if command == "init":
        init.create_gitlet()


if __name__ == "__main__":
    main()

