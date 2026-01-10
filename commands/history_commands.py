import pathlib as Path
import pickle
import getpass
import utils
from utils import Commit
import hashlib 
from commands import main_commands, basic_commands

def revert(hash, message):
    head_tuple = utils.check_head()
    head_hash = head_tuple[4]
    tracked_files = utils.get_commit(head_hash).files

    utils.get_old_commit_state(hash, tracked_files)


    revert_commit_object = utils.get_commit(hash)
    revert_commit_files = revert_commit_object.files

    basic_commands.empty()

    with open(".minigit/index", "rb") as f:
        staging = pickle.load(f)
    
    for file, hash in revert_commit_files.items():
        staging["additions"][file] = hash
    
    with open(".minigit/index", "wb") as f:
        pickle.dump(staging, f)

    if message == None:
        message = f"Reverting to commit {hash}."
    main_commands.commit(message)


def reset():
    pass