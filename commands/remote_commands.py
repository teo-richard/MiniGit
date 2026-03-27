import json
from pathlib import Path
import utils
import shutil
import pickle
from commands.branch_commands import merge

def remote_add(name, path):
    dict = {name: path}

    config_path = Path.cwd() / ".minigit" / "config"
    with open(config_path, "r") as f:
        config = json.load(f)

    config["remotes"][name] = path

    with open(config_path, "w") as f:
        json.dump(config, f)


@utils.check_uncommitted_changes
@utils.check_detached_head_state # Checking to make sure head is attached
def remote_prep_push(name, branch):
    
    # Get the path to the repo and branch the user wants

    path_to_repo, path_to_remote_branch = utils.get_remote_repo_and_branch(name, branch)
    path_to_remote_branch.parent.mkdir(parents=True, exist_ok=True) # Creates the directory heads containing branch files if it doesn't exist already


    # This is the most previous commit hash we have locally
    local_branch_hash = utils.check_head()[4]

    if path_to_remote_branch.exists():
        # Get the most previous commit hash the remote repo has
        remote_branch_hash = utils.open_remote_branch(path_to_remote_branch)

        # Finding common ancestor on the two branches
        # Get ancestors on local branch
        result = utils.find_branch_ancestor(local_branch_hash, remote_branch_hash)
        if result:
            return result, path_to_repo, path_to_remote_branch
    else:
        ancestors_to_push = [local_branch_hash]
        commit_parent = utils.get_commit_parent(local_branch_hash)
        while commit_parent:
            ancestors_to_push.append(commit_parent)
            commit_parent = utils.get_commit_parent(commit_parent)
        return ancestors_to_push, path_to_repo, path_to_remote_branch




def copy_object(obj_hash, src_objects_dir, dst_objects_dir, object_type):
    src = src_objects_dir / object_type / obj_hash[:2] / obj_hash
    dst_dir = dst_objects_dir / object_type / obj_hash[:2]
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / obj_hash
    if not dst.exists():
        shutil.copy(src, dst)



def copy_to_other_repo(src_objects_dir, dst_objects_dir, commit_hashes_to_copy_over):
    for ancestor_hash in commit_hashes_to_copy_over:
        # Copy commit objects over
        copy_object(
            ancestor_hash, 
            src_objects_dir,
            dst_objects_dir,
            "commits"
        )
        commit_path = src_objects_dir / "commits" / ancestor_hash[:2] / ancestor_hash
        with open(commit_path, "rb") as f:
            commit_obj = pickle.load(f)

    # copy over the blobs
        for blob_hash in commit_obj.files.values():
            copy_object(
            blob_hash, 
            src_objects_dir,
            dst_objects_dir,
            "blobs"
        )



def remote_push(ancestors_to_push, path_to_repo, path_to_remote_branch):
    # order of commit hashes in the list ancestors_to_push doesn't matter
    src_objects_dir = Path(".minigit") / "objects"
    dst_objects_dir = path_to_repo / ".minigit" / "objects"
    copy_to_other_repo(src_objects_dir, dst_objects_dir, ancestors_to_push)
    
    # Update the branch tip hash
    with open(path_to_remote_branch, "w") as f:
        f.write(ancestors_to_push[0]) # The most recent commit on the local branch



def fetch(name, branch):
    path_to_repo, path_to_remote_branch = utils.get_remote_repo_and_branch(name, branch)
    remote_branch_hash = utils.open_remote_branch(path_to_remote_branch)
    _, local_branch_hash = utils.check_head()[3:5]

    commits_to_copy = utils.find_branch_ancestor(remote_branch_hash, local_branch_hash)
    try:
        remote_branch_tip_hash = commits_to_copy[0]

        path_to_new_local_branch = Path(f".minigit/refs/{name}/{branch}")
        path_to_new_local_branch.parent.mkdir(parents=True, exist_ok=True)

        with open(path_to_new_local_branch, "w") as f:
            f.write(remote_branch_tip_hash)

        src_objects_dir = path_to_repo / ".minigit" / "objects"
        dst_objects_dir = Path(".minigit") / "objects"

        copy_to_other_repo(src_objects_dir, dst_objects_dir, commits_to_copy)
        print(f"\nFetched commits from {name}, branch {branch} and copied to \"{path_to_new_local_branch}\"")

        return path_to_new_local_branch

    except IndexError: # If commits_to_copy is an empty list
        print("\nAlready up to date. Loser smoooooozer.\n")
        return False


@utils.check_detached_head_state
def pull(name, branch):
    path_to_new_local_branch = fetch(name, branch)
    if path_to_new_local_branch:
        merge(path_to_new_local_branch, f"Merge {name}/{branch}", True)

        print(f"\nSuccessfully merged branch path {path_to_new_local_branch} to branch {utils.check_head()[2]} (your current branch).")
        print("Pull complete.\n")
    else:
        print("\nPull failed because you're already up to date.\n")