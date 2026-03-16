import json
from pathlib import Path
import utils
import shutil
import pickle

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
    # Get the paths to remote repos out of the config file
    with open(".minigit/config", "r") as f:
        config = json.load(f)
    
    # Get the path to the repo and branch the user wants
    path_to_repo = Path(config["remotes"][name])
    path_to_remote_branch = path_to_repo / f".minigit/refs/heads/{branch}"

    # This is the most previous commit hash we have locally
    local_branch_hash = utils.check_head()[4]

    # Get the most previous commit hash the remote repo has
    with open(path_to_remote_branch, "r") as f:
        remote_branch_hash = f.read()

    # Finding common ancestor on the two branches
    # Get ancestors on local branch
    ancestors_to_push = [local_branch_hash]
    try:
        local_commit_parent_hash = utils.get_commit(local_branch_hash).parent[0]
    except IndexError:
        return ancestors_to_push, path_to_repo, path_to_remote_branch
    if local_commit_parent_hash != remote_branch_hash:
        while local_commit_parent_hash:
            if local_commit_parent_hash != remote_branch_hash:
                ancestors_to_push.append(local_commit_parent_hash)
                try:
                    local_commit_parent_hash = utils.get_commit(local_commit_parent_hash).parent[0]
                except IndexError:
                    break
            else:
                break

        return ancestors_to_push, path_to_repo, path_to_remote_branch

    else:
        print("\nYou don't have any new commits to merge sucker. Go do something useful with your life.\n")
            


def copy_object(obj_hash, src_objects_dir, dst_objects_dir, object_type):
    src = src_objects_dir / object_type / obj_hash[:2] / obj_hash
    dst_dir = dst_objects_dir / object_type / obj_hash[:2]
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / obj_hash
    if not dst.exists():
        shutil.copy(src, dst)

def remote_push(ancestors_to_push, path_to_repo, path_to_remote_branch):
    # order of commit hashes in the list ancestors_to_push doesn't matter
    src_objects_dir = Path(".minigit") / "objects"
    dst_objects_dir = path_to_repo / ".minigit" / "objects"
    for ancestor_hash in ancestors_to_push:
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
    
    # Update the branch tip hash
    with open(path_to_remote_branch, "w") as f:
        f.write(ancestors_to_push[0]) # The most recent commit on the local branch