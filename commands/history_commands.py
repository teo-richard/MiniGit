import pickle
from pathlib import Path
import hashlib
import datetime
import os
from colorama import Fore, Style, init
from typing import List

def state_status(filelist: dict | list, message:str, color:str) -> bool:
    colors = {
        "red": Fore.RED,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "blue": Fore.BLUE,
        "magenta": Fore.MAGENTA,
        "cyan": Fore.CYAN,
        "white": Fore.WHITE,
        "orange": Fore.LIGHTYELLOW_EX
    }
    color_code = colors[color]
    print("\n" + message)

    if isinstance(filelist, List):
        for item in filelist:
            print(f"{color_code} {item}{Style.RESET_ALL}")
    else:
        for key, value in filelist.items():
            print(f"{color_code} {value} {key}{Style.RESET_ALL}")


def check_ignore(filepath):
    ignore_patterns = [
        '__pycache__',
        '.pyc',
        'venv/',
        '.git',
        '.minigit',
        '.DS_Store',
    ]

    for pattern in ignore_patterns:
        if pattern in filepath:
            return True
        
    parts = filepath.split(os.sep)
    if any(part.startswith(".") and part != "." for part in parts):
        return True
    
    return False


def status():
    directory_files = {}

    # Fills the dict of all the files and hashes in your directory
    # `dirs` is os.walk's internal list of dirs it will walk to in the starting foldier it's in
    for root, dirs, files in os.walk("."):
        for file in files:
            dirs[:] = [d for d in dirs if not check_ignore(d)] # if check_ignore returns false - this is checking the *directories*
            filepath = os.path.join(root, file)
            if check_ignore(filepath) == True: # Check if the filepath itself should be skipped
                continue
            with open(filepath, "rb") as f:
                file_byte = f.read()

            file_hash = hashlib.sha1(file_byte).hexdigest()
            # Normalize path to remove leading './' and use forward slashes
            normalized_path = filepath.lstrip("./").replace("\\", "/")
            directory_files[normalized_path] = file_hash
    

    # Gets the dictionary that is your staging area
    with open(".minigit/index", "rb") as f:
        staging_area = pickle.load(f) 

    staging_area_additions = staging_area["additions"] # dictionary {file name : hash}
    staging_area_removals = staging_area["removals"] # list [file name, file name, ...]


    # Gets head dictionary and head hash
    head_path = Path(".minigit") / "HEAD"
    with open(head_path, "rb") as f:
        head = pickle.load(f)
    head_hash = head[0] # head is [hash, branch]
    
    # Get the branch hash to check if HEAD is detached
    branch_name = head[1]
    branch_file = Path(".minigit") / "refs" / "heads" / branch_name
    with open(branch_file, "r") as f:
        branch_hash = f.read()

    # Get previous commit files
    path_to_commit = Path(".minigit") / "objects" / "commits" / head_hash[:2] / head_hash
    with open(path_to_commit, "rb") as f:
        prev_commit_obj = pickle.load(f)
    prev_commit_files = prev_commit_obj.files # Dictionary of files

    # Compare staging area files with directory files and commit files to get files that are TRACKED but NOT IN STAGING AREA

    # Get files that are simply tracked but not staged
    all_staged_files = list(staging_area["additions"].keys()) + staging_area["removals"]
    not_staged = {k: v for k, v in directory_files.items() if k not in all_staged_files}
    tracked_not_staged = {k: v for k, v in not_staged.items() if k in prev_commit_files.keys()}

    # Get files in staging area additions that are not in directory files and are UNCHANGED
    unmodified_tracked_not_staged = {k: v for k, v in tracked_not_staged.items() if prev_commit_files.get(k) == v}

    # Get files in staging area additions that are not in directory files and are MODIFIED (i.e. different hashes)
    modified_tracked_not_staged = {k: v for k, v in tracked_not_staged.items() if prev_commit_files.get(k) != v}

    # Get files that aren't tracked
    not_tracked = {k: v for k, v in directory_files.items() 
                    if k not in staging_area_additions 
                    and k not in staging_area_removals 
                    and k not in prev_commit_files}

    # Print out the messages and list the files for the user to see
    if head_hash != branch_hash:
        print(f"Note: head is detached from {branch_name} branch.")
    else:
        print("Head is attached to master.")
    
    print(f"Head: {head_hash}")
    print(f"Head: {branch_name}\n")

    state_status(staging_area["additions"], 
                 "Files in staging area to be added to the next commit:",
                 "green")
    
    state_status(staging_area["removals"], 
                 "Files in staging area to be removed in the next commit:",
                 "blue")
    
    state_status(unmodified_tracked_not_staged,
                 "Tracked files not in staging area that have NOT been modified since last commit:",
                 "cyan")

    state_status(modified_tracked_not_staged,
                 "Tracked files not in staging area that HAVE been modified since last commit:",
                 "orange")
    
    state_status(not_tracked,
                 "Files that are not tracked:",
                 "red")
    
    print("\nI hope you enjoyed this status update. I sure did!\n")


    
