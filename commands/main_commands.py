import os
from pathlib import Path
import datetime
import pickle
import hashlib

class Commit:
    def __init__ (self, message, parent, files, author, timestamp = datetime.datetime.now):
        self.message = message
        self.parent = parent
        self.files = files
        self.author = author
        self.timestamp = timestamp 

def create_minigit():
    current_dir = Path.cwd()
    minigit_dir = current_dir / ".minigit"

    if minigit_dir.exists():
        print("A gitlet folder already exists in the cwd you fooooool")
        return

    # Create .gitlet./
    minigit_dir.mkdir() 
    # Create subdirectories
    (minigit_dir / "objects").mkdir() 
    (minigit_dir / "objects" / "commits").mkdir() 
    (minigit_dir / "objects" / "blobs").mkdir() 
    (minigit_dir / "refs" / "heads").mkdir(parents=True)

    # Create instance of Commit class
    initial_commit = Commit(
        message = "initial commit",
        author = "Teo",
        parent = None,
        files = {}
    )


    # Serialize the commit (i.e. convert to bytes)
    initial_commit_data = pickle.dumps(initial_commit)

    # Hash the commit by chaining hashlib.sha1() to hexdigest()
    initial_commit_hash = hashlib.sha1(initial_commit_data).hexdigest()

    # Create file that will contain your initial commit object (with hash as filename)
    # Storing initial_commit_hash in a folder named using the first two characters of the hash
    object_subdir = minigit_dir / "objects" / "commits" / initial_commit_hash[:2]
    object_subdir.mkdir()
    commit_file = object_subdir / initial_commit_hash

    # Write it to the correct directory
    # Write the initial commit data (your commit dictionary repr. as bytes) in the initial commit file
    with open(commit_file, "wb") as f: # "wb" for writing bytes
        f.write(initial_commit_data)

    # Create master branch
    master_branch = minigit_dir / "refs" / "heads" / "master"
    with open(master_branch, "w") as f: # "w" for writing text
        f.write(initial_commit_hash)


    # Create empty staging area
    index_file = minigit_dir / "index" # Creates a path object
    empty_dict = {} # Write empty dictionary to the file to be filled later

    # Create index_file as a FILE and put the empty dictionary in there
    with open(index_file, "wb") as f:
        pickle.dump(empty_dict, f) # Pickles the empty_dict and puts it in the file
    
    print("Initialized MiniGit repository. Go ham. ")


def stage(filelist):
    index_file = Path(".minigit") / "index"

    with open(index_file, "rb") as f:
        staging = pickle.load(f)

        for filename in filelist:
            filepath = Path(filename)

            if not filepath.exists():
                print(f"File {filename} does not exist")
            
            with open(filepath, "rb") as f:
                file_content = f.read()

            file_hash = hashlib.sha1(file_content).hexdigest()