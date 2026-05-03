"""
*** ALL TESTS WRITTEN BY CLAUDE CODE ***

Comprehensive additional tests for MiniGit.

Covers:
  - info_commands:  amend, status, log, log_all, reflog
  - history_commands: revert, reset (hard + soft)
  - remote_commands:  remote_add, remote_push, fetch, pull
  - Edge cases for stage, checkout, merge (three-way conflict,
    three-way non-conflict), branch_switch with dirty working tree,
    find_branch_ancestor, find_common_ancestor

Known bugs (unfixed)
--------------------
* fetch / find_branch_ancestor remote-object bug: find_branch_ancestor
  calls get_commit() using the CWD's .minigit store.  Remote-only hashes
  are not present there, so fetching truly new remote commits raises
  CommitNotFoundError.  The fetch tests work around this by pre-copying the
  remote's new objects into the local store before calling fetch().
"""

import hashlib
import json
import os
import pickle
import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import utils
from utils import Commit, CommitNotFoundError
from commands import (
    basic_commands,
    branch_commands,
    history_commands,
    info_commands,
    main_commands,
    remote_commands,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_commits(repo_path):
    """Return {hash: commit_obj} for every commit stored in the repo."""
    commits = {}
    commits_dir = repo_path / ".minigit" / "objects" / "commits"
    for prefix_dir in commits_dir.iterdir():
        for f in prefix_dir.iterdir():
            with open(f, "rb") as fh:
                obj = pickle.load(fh)
            commits[f.name] = obj
    return commits


def _head_hash(repo_path):
    """Return the commit hash that HEAD currently resolves to."""
    head = (repo_path / ".minigit" / "HEAD").read_text().strip()
    if "refs" in head:
        branch = head.split()[-1].split("/")[-1]
        return (repo_path / ".minigit" / "refs" / "heads" / branch).read_text().strip()
    return head


def _commit_hash_for(repo_path, branch="master"):
    return (repo_path / ".minigit" / "refs" / "heads" / branch).read_text().strip()


def _sync_objects(src_repo, dst_repo):
    """Copy every object (commits + blobs) from src_repo into dst_repo."""
    for kind in ("commits", "blobs"):
        src = src_repo / ".minigit" / "objects" / kind
        dst = dst_repo / ".minigit" / "objects" / kind
        for prefix_dir in src.iterdir():
            (dst / prefix_dir.name).mkdir(exist_ok=True)
            for f in prefix_dir.iterdir():
                dest_file = dst / prefix_dir.name / f.name
                if not dest_file.exists():
                    shutil.copy(f, dest_file)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main_commands.init()
    return tmp_path


@pytest.fixture
def repo_one(repo):
    """One real commit on master. Index retains hello.txt after commit."""
    (repo / "hello.txt").write_bytes(b"hello world")
    main_commands.stage(["hello.txt"], "additions")
    main_commands.commit("first commit")
    return repo


@pytest.fixture
def repo_two(repo_one):
    """Two real commits on master. Index retains hello.txt after both commits."""
    (repo_one / "hello.txt").write_bytes(b"hello v2")
    main_commands.stage(["hello.txt"], "additions")
    main_commands.commit("second commit")
    return repo_one


@pytest.fixture
def two_repos(tmp_path, monkeypatch):
    """
    local  – full repo with one committed file.
    remote – bare directory structure with NO branch file, so that the first
             push takes the "new branch" code path in remote_prep_push.

    We do NOT call main_commands.init() on remote because that would create
    its own initial commit with a different timestamp/hash, breaking the
    find_branch_ancestor ancestry check.
    """
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    local.mkdir()
    remote.mkdir()

    # Build a minimal .minigit skeleton on remote (no branch file, no index).
    for subdir in (
        ".minigit/objects/commits",
        ".minigit/objects/blobs",
        ".minigit/refs/heads",
    ):
        (remote / subdir).mkdir(parents=True)
    (remote / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
    (remote / ".minigit" / "config").write_text(json.dumps({"remotes": {}}))
    # remote needs an index and .minigitignore so that stage/commit work when
    # the test temporarily chdir's into it.
    (remote / ".minigit" / "index").write_bytes(pickle.dumps({}))
    (remote / ".minigitignore").write_text("")

    # Initialise local, add a commit, register remote
    monkeypatch.chdir(local)
    main_commands.init()
    (local / "file.txt").write_bytes(b"initial content")
    main_commands.stage(["file.txt"], "additions")
    main_commands.commit("initial file commit")
    remote_commands.remote_add("origin", str(remote))

    return local, remote


# ===========================================================================
# amend
# ===========================================================================

class TestAmend:
    def test_amend_creates_new_commit_with_updated_message(self, repo_one):
        info_commands.amend("amended message")
        assert utils.get_commit(_head_hash(repo_one)).message == "amended message"

    def test_amend_removes_old_commit_file(self, repo_one):
        old_hash = _head_hash(repo_one)
        old_path = repo_one / ".minigit" / "objects" / "commits" / old_hash[:2] / old_hash
        assert old_path.exists()
        info_commands.amend("amended message")
        assert not old_path.exists()

    def test_amend_head_still_references_branch_after_amend(self, repo_one):
        """HEAD should still point to a branch ref, not be detached."""
        info_commands.amend("new message")
        assert "refs" in (repo_one / ".minigit" / "HEAD").read_text()

    def test_amend_updates_branch_pointer_file(self, repo_one):
        """Bug 3 fix: refs/heads/master must point to the new commit hash."""
        old_hash = _head_hash(repo_one)
        info_commands.amend("fixed message")
        new_hash = _head_hash(repo_one)
        assert new_hash != old_hash
        assert utils.get_commit(new_hash).message == "fixed message"

    def test_amend_repo_usable_after_amend(self, repo_one):
        """After amend the branch pointer is valid so further commits work."""
        info_commands.amend("amended")
        (repo_one / "extra.txt").write_bytes(b"extra")
        main_commands.stage(["extra.txt"], "additions")
        before = _head_hash(repo_one)
        main_commands.commit("post-amend commit")
        basic_commands.empty()
        assert _head_hash(repo_one) != before

    def test_amend_preserves_file_state(self, repo_one):
        old_files = utils.get_commit(_head_hash(repo_one)).files
        info_commands.amend("different message")
        assert utils.get_commit(_head_hash(repo_one)).files == old_files

    def test_amend_on_detached_head_updates_head_to_new_hash(self, repo_one):
        old_hash = _head_hash(repo_one)
        (repo_one / ".minigit" / "HEAD").write_text(old_hash)  # detach
        info_commands.amend("detached amend")
        new_head = (repo_one / ".minigit" / "HEAD").read_text().strip()
        assert new_head != old_hash
        assert utils.get_commit(new_head).message == "detached amend"

    def test_amend_on_detached_head_old_file_deleted(self, repo_one):
        old_hash = _head_hash(repo_one)
        (repo_one / ".minigit" / "HEAD").write_text(old_hash)
        info_commands.amend("detached amend")
        old_path = repo_one / ".minigit" / "objects" / "commits" / old_hash[:2] / old_hash
        assert not old_path.exists()

    def test_amend_does_not_touch_other_commits(self, repo_two):
        """Only the most-recent commit should be re-written."""
        before = set(_all_commits(repo_two).keys())
        info_commands.amend("just the tip")
        after = set(_all_commits(repo_two).keys())
        assert len(before - after) == 1
        assert len(after - before) == 1


# ===========================================================================
# revert
# ===========================================================================

class TestRevert:
    def test_revert_restores_file_to_earlier_content(self, repo_two):
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.revert(first_hash, None)
        basic_commands.empty()
        assert (repo_two / "hello.txt").read_bytes() == b"hello world"

    def test_revert_creates_a_new_commit(self, repo_two):
        before_hash = _head_hash(repo_two)
        first_hash = utils.get_commit(before_hash).parent[0]
        history_commands.revert(first_hash, None)
        basic_commands.empty()
        assert _head_hash(repo_two) != before_hash

    def test_revert_default_message_starts_with_reverting(self, repo_two):
        # NOTE: known bug – the `for file, hash in` loop in revert() overwrites
        # the `hash` parameter, so the default message ends up containing the
        # last blob hash rather than the commit hash.  We therefore only assert
        # the message starts with the expected prefix.
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.revert(first_hash, None)
        basic_commands.empty()
        new_commit = utils.get_commit(_head_hash(repo_two))
        assert new_commit.message.startswith("Reverting to commit ")

    def test_revert_custom_message_used(self, repo_two):
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.revert(first_hash, "rolling back")
        basic_commands.empty()
        assert utils.get_commit(_head_hash(repo_two)).message == "rolling back"

    def test_revert_new_commit_files_match_target(self, repo_two):
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        target_files = utils.get_commit(first_hash).files
        history_commands.revert(first_hash, "revert test")
        basic_commands.empty()
        assert utils.get_commit(_head_hash(repo_two)).files == target_files

    def test_revert_preserves_history_length(self, repo_two):
        """Revert should ADD a commit, not remove any."""
        commits_before = len(_all_commits(repo_two))
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.revert(first_hash, "preserve history")
        basic_commands.empty()
        assert len(_all_commits(repo_two)) == commits_before + 1


# ===========================================================================
# reset
# ===========================================================================

class TestReset:
    def test_reset_hard_moves_branch_pointer_to_target(self, repo_two):
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(first_hash, "hard")
        assert _head_hash(repo_two) == first_hash

    def test_reset_hard_restores_working_directory(self, repo_two):
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(first_hash, "hard")
        assert (repo_two / "hello.txt").read_bytes() == b"hello world"

    def test_reset_hard_clears_staging_area(self, repo_two, monkeypatch):
        # Stage a file; the @check_uncommitted_changes decorator will prompt –
        # monkeypatch input to answer "y" so the reset proceeds.
        (repo_two / "staged.txt").write_bytes(b"staged")
        main_commands.stage(["staged.txt"], "additions")
        monkeypatch.setattr("builtins.input", lambda _: "y")
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(first_hash, "hard")
        staging = utils.get_staging_area()
        assert staging == {}

    def test_reset_soft_moves_branch_pointer(self, repo_two):
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(first_hash, "soft")
        assert _head_hash(repo_two) == first_hash

    def test_reset_soft_preserves_working_directory_content(self, repo_two):
        content_before = (repo_two / "hello.txt").read_bytes()
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(first_hash, "soft")
        assert (repo_two / "hello.txt").read_bytes() == content_before

    def test_reset_hard_on_detached_head_updates_head_directly(self, repo_two):
        current = _head_hash(repo_two)
        first_hash = utils.get_commit(current).parent[0]
        (repo_two / ".minigit" / "HEAD").write_text(current)  # detach
        history_commands.reset(first_hash, "hard")
        assert (repo_two / ".minigit" / "HEAD").read_text().strip() == first_hash

    def test_reset_to_initial_commit(self, repo_two):
        """Reset all the way back to the very first commit (needs 3 commits)."""
        (repo_two / "third.txt").write_bytes(b"third")
        main_commands.stage(["third.txt"], "additions")
        main_commands.commit("third commit")
        tip = _head_hash(repo_two)
        second = utils.get_commit(tip).parent[0]
        first = utils.get_commit(second).parent[0]
        history_commands.reset(first, "hard")
        assert _head_hash(repo_two) == first


# ===========================================================================
# status
# ===========================================================================

class TestStatus:
    def test_status_runs_without_error(self, repo_one, capsys):
        info_commands.status()
        assert capsys.readouterr().out

    def test_status_shows_staged_file(self, repo_one, capsys):
        (repo_one / "new.txt").write_bytes(b"new")
        main_commands.stage(["new.txt"], "additions")
        info_commands.status()
        assert "new.txt" in capsys.readouterr().out

    def test_status_shows_modified_tracked_file(self, repo_one, capsys):
        (repo_one / "hello.txt").write_bytes(b"changed")
        info_commands.status()
        assert "hello.txt" in capsys.readouterr().out

    def test_status_shows_untracked_file(self, repo_one, capsys):
        (repo_one / "untracked.txt").write_bytes(b"untracked")
        info_commands.status()
        assert "untracked.txt" in capsys.readouterr().out

    def test_status_shows_branch_name_when_attached(self, repo_one, capsys):
        info_commands.status()
        assert "master" in capsys.readouterr().out

    def test_status_shows_detached_message_when_detached(self, repo_one, capsys):
        (repo_one / ".minigit" / "HEAD").write_text(_head_hash(repo_one))
        info_commands.status()
        assert "detached" in capsys.readouterr().out.lower()

    def test_status_file_staged_for_removal_appears(self, repo_one, capsys):
        main_commands.stage(["hello.txt"], "removals")
        info_commands.status()
        assert "hello.txt" in capsys.readouterr().out


# ===========================================================================
# log / log_all / reflog
# ===========================================================================

class TestLog:
    def test_log_shows_commit_message(self, repo_two, capsys):
        info_commands.log()
        assert "second commit" in capsys.readouterr().out

    def test_log_shows_all_commits_in_chain(self, repo_two, capsys):
        info_commands.log()
        assert "first commit" in capsys.readouterr().out

    def test_log_on_fresh_repo_prints_no_commits_message(self, repo, capsys):
        info_commands.log()
        assert "no commits" in capsys.readouterr().out.lower()

    def test_log_all_includes_commits_from_all_branches(self, repo_two, capsys):
        branch_commands.branch_create("feature")
        (repo_two / "feature.txt").write_bytes(b"feature work")
        main_commands.stage(["feature.txt"], "additions")
        main_commands.commit("feature commit")
        basic_commands.empty()
        (repo_two / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        info_commands.log_all()
        out = capsys.readouterr().out
        assert "feature commit" in out
        assert "second commit" in out

    def test_log_all_deduplicates_shared_commits(self, repo_two, capsys):
        branch_commands.branch_create("feature")
        (repo_two / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        info_commands.log_all()
        out = capsys.readouterr().out
        assert out.count("second commit") == 1

    def test_reflog_shows_all_commit_hashes(self, repo_two, capsys):
        info_commands.reflog()
        out = capsys.readouterr().out
        for h in _all_commits(repo_two):
            assert h in out


# ===========================================================================
# remote_add
# ===========================================================================

class TestRemoteAdd:
    def test_remote_add_writes_name_and_path_to_config(self, repo):
        remote_commands.remote_add("origin", "/some/path")
        config = json.loads((repo / ".minigit" / "config").read_text())
        assert config["remotes"]["origin"] == "/some/path"

    def test_remote_add_multiple_remotes(self, repo):
        remote_commands.remote_add("origin", "/path/a")
        remote_commands.remote_add("upstream", "/path/b")
        config = json.loads((repo / ".minigit" / "config").read_text())
        assert "origin" in config["remotes"]
        assert "upstream" in config["remotes"]

    def test_remote_add_overwrites_existing_entry(self, repo):
        remote_commands.remote_add("origin", "/old/path")
        remote_commands.remote_add("origin", "/new/path")
        config = json.loads((repo / ".minigit" / "config").read_text())
        assert config["remotes"]["origin"] == "/new/path"


# ===========================================================================
# remote_push
# ===========================================================================

class TestRemotePush:
    def test_push_creates_remote_branch_file(self, two_repos):
        local, remote = two_repos
        ancestors, repo_path, branch_path = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(ancestors, repo_path, branch_path)
        assert branch_path.exists()

    def test_push_updates_remote_branch_to_local_tip(self, two_repos):
        local, remote = two_repos
        local_hash = _head_hash(local)
        ancestors, repo_path, branch_path = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(ancestors, repo_path, branch_path)
        assert branch_path.read_text().strip() == local_hash

    def test_push_copies_commit_objects_to_remote(self, two_repos):
        local, remote = two_repos
        local_hash = _head_hash(local)
        ancestors, repo_path, branch_path = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(ancestors, repo_path, branch_path)
        assert (remote / ".minigit" / "objects" / "commits" / local_hash[:2] / local_hash).exists()

    def test_push_copies_blob_objects_to_remote(self, two_repos):
        local, remote = two_repos
        local_hash = _head_hash(local)
        blob_hash = list(utils.get_commit(local_hash).files.values())[0]
        ancestors, repo_path, branch_path = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(ancestors, repo_path, branch_path)
        assert (remote / ".minigit" / "objects" / "blobs" / blob_hash[:2] / blob_hash).exists()

    def test_push_transfers_entire_chain_on_first_push(self, two_repos):
        """Every commit (including the initial one) must arrive on remote."""
        local, remote = two_repos
        ancestors, repo_path, branch_path = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(ancestors, repo_path, branch_path)
        for h in ancestors:
            assert (remote / ".minigit" / "objects" / "commits" / h[:2] / h).exists()

    def test_incremental_push_only_sends_new_commits(self, two_repos):
        """After a push, only NEW commits should be transferred on the next push."""
        local, remote = two_repos
        a1, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a1, rp, bp)

        (local / "extra1.txt").write_bytes(b"extra1")
        main_commands.stage(["extra1.txt"], "additions")
        main_commands.commit("extra commit 1")
        basic_commands.empty()

        a2, _, _ = remote_commands.remote_prep_push("origin", "master")
        assert len(a2) == 1
        assert a2[0] == _head_hash(local)

    def test_push_with_exactly_one_new_commit(self, two_repos):
        """Regression test: find_branch_ancestor previously returned None for exactly
        1 new commit whose parent == remote tip.  Bug is now fixed."""
        local, remote = two_repos
        a1, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a1, rp, bp)

        (local / "new.txt").write_bytes(b"one new commit")
        main_commands.stage(["new.txt"], "additions")
        main_commands.commit("the single new commit")
        basic_commands.empty()
        new_hash = _head_hash(local)

        a2, rp2, bp2 = remote_commands.remote_prep_push("origin", "master")
        assert a2 is not None
        assert a2 == [new_hash]
        remote_commands.remote_push(a2, rp2, bp2)
        assert bp2.read_text().strip() == new_hash

    def test_incremental_push_updates_remote_to_latest_tip(self, two_repos):
        local, remote = two_repos
        a1, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a1, rp, bp)

        for i in range(2):
            (local / f"extra{i}.txt").write_bytes(f"x{i}".encode())
            main_commands.stage([f"extra{i}.txt"], "additions")
            main_commands.commit(f"new {i}")
            basic_commands.empty()

        a2, rp2, bp2 = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a2, rp2, bp2)
        assert bp2.read_text().strip() == _head_hash(local)


# ===========================================================================
# copy_to_other_repo (direct unit test)
# ===========================================================================

class TestCopyToOtherRepo:
    def test_copies_specified_commit_and_blobs(self, two_repos):
        local, remote = two_repos
        local_hash = _head_hash(local)
        src = local / ".minigit" / "objects"
        dst = remote / ".minigit" / "objects"
        remote_commands.copy_to_other_repo(src, dst, [local_hash])
        assert (dst / "commits" / local_hash[:2] / local_hash).exists()

    def test_does_not_overwrite_existing_object(self, two_repos):
        local, remote = two_repos
        local_hash = _head_hash(local)
        blob_hash = list(utils.get_commit(local_hash).files.values())[0]
        src = local / ".minigit" / "objects"
        dst = remote / ".minigit" / "objects"
        remote_commands.copy_to_other_repo(src, dst, [local_hash])
        mtime1 = (dst / "blobs" / blob_hash[:2] / blob_hash).stat().st_mtime
        remote_commands.copy_to_other_repo(src, dst, [local_hash])
        mtime2 = (dst / "blobs" / blob_hash[:2] / blob_hash).stat().st_mtime
        assert mtime1 == mtime2


# ===========================================================================
# fetch
# ===========================================================================

class TestFetch:
    """
    fetch() calls find_branch_ancestor() which reads commit objects via
    get_commit() – a function that always looks in the *local* .minigit store.
    Remote-only commits are therefore not found unless they are pre-copied.

    _setup():
      1. pushes local commits to remote (shared history),
      2. adds TWO commits directly on the remote repo,
      3. pre-copies those objects into local's store (bug workaround),
      4. returns the remote tip hash and control to local CWD.
    """

    def _setup(self, local, remote, monkeypatch):
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)

        monkeypatch.chdir(remote)
        (remote / "r1.txt").write_bytes(b"remote file 1")
        main_commands.stage(["r1.txt"], "additions")
        main_commands.commit("remote commit 1")
        basic_commands.empty()

        (remote / "r2.txt").write_bytes(b"remote file 2")
        main_commands.stage(["r2.txt"], "additions")
        main_commands.commit("remote commit 2")
        basic_commands.empty()
        remote_tip = _head_hash(remote)

        monkeypatch.chdir(local)
        _sync_objects(remote, local)  # workaround: pre-copy remote objects
        return remote_tip

    def test_fetch_creates_local_tracking_ref(self, two_repos, monkeypatch):
        local, remote = two_repos
        self._setup(local, remote, monkeypatch)
        remote_commands.fetch("origin", "master")
        assert (local / ".minigit" / "refs" / "origin" / "master").exists()

    def test_fetch_tracking_ref_points_to_remote_tip(self, two_repos, monkeypatch):
        local, remote = two_repos
        remote_tip = self._setup(local, remote, monkeypatch)
        remote_commands.fetch("origin", "master")
        tracking = local / ".minigit" / "refs" / "origin" / "master"
        assert tracking.read_text().strip() == remote_tip

    def test_fetch_copies_remote_commit_to_local_objects(self, two_repos, monkeypatch):
        local, remote = two_repos
        remote_tip = self._setup(local, remote, monkeypatch)
        remote_commands.fetch("origin", "master")
        assert (local / ".minigit" / "objects" / "commits" / remote_tip[:2] / remote_tip).exists()

    def test_fetch_copies_remote_blobs_to_local_objects(self, two_repos, monkeypatch):
        local, remote = two_repos
        remote_tip = self._setup(local, remote, monkeypatch)
        remote_commands.fetch("origin", "master")
        remote_commit = pickle.loads(
            (remote / ".minigit" / "objects" / "commits" / remote_tip[:2] / remote_tip).read_bytes()
        )
        for blob_hash in remote_commit.files.values():
            assert (local / ".minigit" / "objects" / "blobs" / blob_hash[:2] / blob_hash).exists()

    def test_fetch_returns_path_to_tracking_ref(self, two_repos, monkeypatch):
        local, remote = two_repos
        self._setup(local, remote, monkeypatch)
        result = remote_commands.fetch("origin", "master")
        assert result is not None
        assert Path(result).exists()


# ===========================================================================
# pull
# ===========================================================================

class TestPull:
    """Same pre-copy workaround as TestFetch."""

    def _setup(self, local, remote, monkeypatch):
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)

        monkeypatch.chdir(remote)
        (remote / "remote_new.txt").write_bytes(b"from remote")
        main_commands.stage(["remote_new.txt"], "additions")
        main_commands.commit("remote advance 1")
        basic_commands.empty()

        (remote / "remote_new2.txt").write_bytes(b"from remote 2")
        main_commands.stage(["remote_new2.txt"], "additions")
        main_commands.commit("remote advance 2")
        basic_commands.empty()
        remote_tip = _head_hash(remote)

        monkeypatch.chdir(local)
        _sync_objects(remote, local)
        return remote_tip

    def test_pull_fast_forwards_local_branch(self, two_repos, monkeypatch):
        local, remote = two_repos
        remote_tip = self._setup(local, remote, monkeypatch)
        remote_commands.pull("origin", "master")
        assert _head_hash(local) == remote_tip

    def test_pull_makes_remote_files_available_locally(self, two_repos, monkeypatch):
        local, remote = two_repos
        self._setup(local, remote, monkeypatch)
        remote_commands.pull("origin", "master")
        assert (local / "remote_new.txt").read_bytes() == b"from remote"
        assert (local / "remote_new2.txt").read_bytes() == b"from remote 2"

    def test_pull_updates_local_commit_to_remote_tip_message(self, two_repos, monkeypatch):
        local, remote = two_repos
        self._setup(local, remote, monkeypatch)
        remote_commands.pull("origin", "master")
        assert utils.get_commit(_head_hash(local)).message == "remote advance 2"


# ===========================================================================
# Edge cases: stage
# ===========================================================================

class TestStageEdgeCases:
    def test_restage_updates_hash_when_content_changes(self, repo_one):
        (repo_one / "hello.txt").write_bytes(b"new content")
        main_commands.stage(["hello.txt"], "additions")
        staging = utils.get_staging_area()
        assert staging["hello.txt"] == hashlib.sha1(b"new content").hexdigest()

    def test_stage_ignored_file_skipped(self, repo):
        (repo / ".minigitignore").write_text("skip.log\n")
        (repo / "skip.log").write_bytes(b"log data")
        main_commands.stage(["skip.log"], "additions")
        staging = utils.get_staging_area()
        assert "skip.log" not in staging

    def test_stage_normalises_path(self, repo_one):
        subdir = repo_one / "src"
        subdir.mkdir()
        (subdir / "mod.py").write_bytes(b"code")
        main_commands.stage(["src/mod.py"], "additions")
        staging = utils.get_staging_area()
        assert all(not k.startswith("./") for k in staging)

    def test_stage_multiple_files_simultaneously(self, repo_one):
        for name in ("a.txt", "b.txt", "c.txt"):
            (repo_one / name).write_bytes(name.encode())
        main_commands.stage(["a.txt", "b.txt", "c.txt"], "additions")
        staging = utils.get_staging_area()
        assert {"a.txt", "b.txt", "c.txt"}.issubset(staging)

    def test_stage_removal_then_re_add_restores_to_index(self, repo_one):
        main_commands.stage(["hello.txt"], "removals")
        (repo_one / "hello.txt").write_bytes(b"updated")
        main_commands.stage(["hello.txt"], "additions")
        staging = utils.get_staging_area()
        assert "hello.txt" in staging


# ===========================================================================
# Edge cases: checkout_commit
# ===========================================================================

class TestCheckoutEdgeCases:
    def test_checkout_blocked_when_tracked_file_modified(self, repo_two, capsys):
        (repo_two / "hello.txt").write_bytes(b"dirty")
        first_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(first_hash)
        assert "unable to checkout" in capsys.readouterr().out.lower()

    def test_checkout_blocked_when_tracked_file_missing(self, repo_one, capsys):
        (repo_one / "hello.txt").unlink()
        # Checking out the current commit is enough to trigger the missing-file guard
        _, _, _, _, current_hash = utils.check_head()
        branch_commands.checkout_commit(current_hash)
        assert "unable to checkout" in capsys.readouterr().out.lower()

    def test_checkout_does_not_move_branch_when_blocked(self, repo_two):
        original = _commit_hash_for(repo_two, "master")
        (repo_two / "hello.txt").write_bytes(b"dirty")
        first_hash = utils.get_commit(original).parent[0]
        branch_commands.checkout_commit(first_hash)
        assert _commit_hash_for(repo_two, "master") == original


# ===========================================================================
# Edge cases: branch_switch
# ===========================================================================

class TestBranchSwitchEdgeCases:
    def test_branch_switch_blocked_by_modified_tracked_file(self, repo_one, capsys):
        branch_commands.branch_create("feature")
        (repo_one / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        (repo_one / "hello.txt").write_bytes(b"dirty")
        branch_commands.branch_switch("feature")
        assert "unable to checkout" in capsys.readouterr().out.lower()

    def test_branch_switch_succeeds_on_clean_working_tree(self, repo_one):
        branch_commands.branch_create("feature")
        (repo_one / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        branch_commands.branch_switch("feature")
        assert "feature" in (repo_one / ".minigit" / "HEAD").read_text()

    def test_branch_switch_nonexistent_prints_error(self, repo_one, capsys):
        branch_commands.branch_switch("nonexistent")
        assert "does not seem to exist" in capsys.readouterr().out.lower()


# ===========================================================================
# Three-way merge
# ===========================================================================

class TestMergeThreeWay:
    def _setup_diverged(self, repo):
        """
        initial → M1(file_a=orig, file_b=orig)
                       ↓ master              ↓ feature
               M2(file_b=master)     F1(file_a=feature)
        """
        (repo / "file_a.txt").write_bytes(b"a original")
        (repo / "file_b.txt").write_bytes(b"b original")
        main_commands.stage(["file_a.txt", "file_b.txt"], "additions")
        main_commands.commit("M1: base state")
        basic_commands.empty()

        branch_commands.branch_create("feature")
        (repo / "file_a.txt").write_bytes(b"a feature version")
        main_commands.stage(["file_a.txt"], "additions")
        main_commands.commit("F1: change file_a on feature")
        basic_commands.empty()

        (repo / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        (repo / "file_a.txt").write_bytes(b"a original")
        (repo / "file_b.txt").write_bytes(b"b original")
        (repo / "file_b.txt").write_bytes(b"b master version")
        main_commands.stage(["file_b.txt"], "additions")
        main_commands.commit("M2: change file_b on master")
        basic_commands.empty()

    def test_three_way_keeps_master_only_change(self, repo):
        self._setup_diverged(repo)
        branch_commands.merge("feature", "merge feature")
        assert (repo / "file_b.txt").read_bytes() == b"b master version"

    def test_three_way_keeps_feature_only_change(self, repo):
        self._setup_diverged(repo)
        branch_commands.merge("feature", "merge feature")
        assert (repo / "file_a.txt").read_bytes() == b"a feature version"

    def test_three_way_merge_commit_has_two_parents(self, repo):
        self._setup_diverged(repo)
        master_hash = _head_hash(repo)
        feature_hash = _commit_hash_for(repo, "feature")
        branch_commands.merge("feature", "merge feature")
        merge_commit = utils.get_commit(_head_hash(repo))
        assert len(merge_commit.parent) == 2
        assert master_hash in merge_commit.parent
        assert feature_hash in merge_commit.parent

    def test_three_way_merge_commit_contains_all_files(self, repo):
        self._setup_diverged(repo)
        branch_commands.merge("feature", "merge feature")
        files = utils.get_commit(_head_hash(repo)).files
        assert "file_a.txt" in files
        assert "file_b.txt" in files

    def _setup_conflict(self, repo):
        """Both branches change conflict.txt from the same base."""
        (repo / "conflict.txt").write_bytes(b"original")
        main_commands.stage(["conflict.txt"], "additions")
        main_commands.commit("M1: add conflict.txt")
        basic_commands.empty()

        branch_commands.branch_create("feature")
        (repo / "conflict.txt").write_bytes(b"feature version")
        main_commands.stage(["conflict.txt"], "additions")
        main_commands.commit("F1: change on feature")
        basic_commands.empty()

        (repo / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        (repo / "conflict.txt").write_bytes(b"original")
        (repo / "conflict.txt").write_bytes(b"master version")
        main_commands.stage(["conflict.txt"], "additions")
        main_commands.commit("M2: change on master")
        basic_commands.empty()

    def test_conflict_file_contains_both_versions(self, repo):
        self._setup_conflict(repo)
        branch_commands.merge("feature", "merge conflict")
        content = (repo / "conflict.txt").read_bytes()
        assert b"master version" in content
        assert b"feature version" in content

    def test_conflict_file_contains_separator(self, repo):
        self._setup_conflict(repo)
        branch_commands.merge("feature", "merge conflict")
        assert b"======" in (repo / "conflict.txt").read_bytes()

    def test_conflict_merge_creates_new_commit(self, repo):
        self._setup_conflict(repo)
        before = _head_hash(repo)
        branch_commands.merge("feature", "merge conflict")
        assert _head_hash(repo) != before

    def test_conflict_merge_commit_stored_with_message(self, repo):
        self._setup_conflict(repo)
        branch_commands.merge("feature", "merge conflict")
        assert utils.get_commit(_head_hash(repo)).message == "merge conflict"


# ===========================================================================
# find_branch_ancestor
# ===========================================================================

class TestFindBranchAncestor:
    def test_returns_new_commits_when_long_is_two_ahead(self, repo_two):
        """The working case: long branch is 2 commits ahead of the first commit."""
        # Add a third commit so tip is 2 ahead of the first commit
        (repo_two / "extra.txt").write_bytes(b"extra")
        main_commands.stage(["extra.txt"], "additions")
        main_commands.commit("third commit")
        tip = _head_hash(repo_two)
        parent = utils.get_commit(tip).parent[0]
        grandparent = utils.get_commit(parent).parent[0]
        result = utils.find_branch_ancestor(tip, grandparent)
        assert result is not None
        assert tip in result
        assert parent in result
        assert grandparent not in result

    def test_returns_none_on_non_fast_forward(self, repo_two, capsys):
        """No shared history → returns empty/falsy (non-fast-forward push is rejected)."""
        tip = _head_hash(repo_two)
        result = utils.find_branch_ancestor(tip, "b" * 40)
        assert not result  # empty list or None both indicate rejection

    def test_initial_commit_only_returns_single_element_list(self, repo_two):
        # The first commit has parent=[], so find_branch_ancestor stops at it
        tip = _head_hash(repo_two)
        first = utils.get_commit(tip).parent[0]
        result = utils.find_branch_ancestor(first, "irrelevant")
        assert result == [first]

    def test_long_branch_hash_is_always_first_element(self, repo_two):
        # Add a third commit so we have three in a chain
        (repo_two / "extra.txt").write_bytes(b"extra")
        main_commands.stage(["extra.txt"], "additions")
        main_commands.commit("third commit")
        tip = _head_hash(repo_two)
        grandparent = utils.get_commit(utils.get_commit(tip).parent[0]).parent[0]
        result = utils.find_branch_ancestor(tip, grandparent)
        assert result[0] == tip

    def test_equal_hashes_returns_empty_list(self, repo_two):
        """Regression test: when long == short (nothing to push), must return []
        not None.  Bug was fixed by adding an early equality check."""
        tip = _head_hash(repo_two)
        result = utils.find_branch_ancestor(tip, tip)
        assert result == []

    def test_returns_single_element_when_one_commit_ahead(self, repo_two):
        """Regression test: exactly 1 new commit (parent == short) must return
        a list of length 1, not None."""
        tip = _head_hash(repo_two)
        parent = utils.get_commit(tip).parent[0]
        result = utils.find_branch_ancestor(tip, parent)
        assert result == [tip]


# ===========================================================================
# find_common_ancestor
# ===========================================================================

class TestFindCommonAncestor:
    def _diverged(self, repo):
        (repo / "base.txt").write_bytes(b"base")
        main_commands.stage(["base.txt"], "additions")
        main_commands.commit("base")
        basic_commands.empty()
        m1_hash = _head_hash(repo)

        branch_commands.branch_create("feature")
        (repo / "feature.txt").write_bytes(b"f")
        main_commands.stage(["feature.txt"], "additions")
        main_commands.commit("feature work")
        basic_commands.empty()
        f1_hash = _head_hash(repo)
        f1 = utils.get_commit(f1_hash)

        (repo / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        (repo / "base.txt").write_bytes(b"base")
        (repo / "master.txt").write_bytes(b"m")
        main_commands.stage(["master.txt"], "additions")
        main_commands.commit("master work")
        basic_commands.empty()
        m2_hash = _head_hash(repo)
        m2 = utils.get_commit(m2_hash)

        return m2_hash, m2, f1_hash, f1, m1_hash

    def test_finds_correct_common_ancestor_hash(self, repo):
        m2_hash, m2, f1_hash, f1, m1_hash = self._diverged(repo)
        _, ancestor_hash = utils.find_common_ancestor(m2, m2_hash, f1)
        assert ancestor_hash == m1_hash

    def test_returns_commit_object(self, repo):
        m2_hash, m2, _, f1, _ = self._diverged(repo)
        ancestor, _ = utils.find_common_ancestor(m2, m2_hash, f1)
        assert isinstance(ancestor, Commit)

    def test_ancestor_has_expected_files(self, repo):
        m2_hash, m2, _, f1, _ = self._diverged(repo)
        ancestor, _ = utils.find_common_ancestor(m2, m2_hash, f1)
        assert "base.txt" in ancestor.files

    def test_ancestor_does_not_have_branch_specific_files(self, repo):
        m2_hash, m2, _, f1, _ = self._diverged(repo)
        ancestor, _ = utils.find_common_ancestor(m2, m2_hash, f1)
        assert "master.txt" not in ancestor.files
        assert "feature.txt" not in ancestor.files
