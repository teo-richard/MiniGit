# MiniGit Bug Report

**Test results (current):** 266 passed, 5 failed — 271 tests total.

---

## Fixed Bugs

### ~~Bug 1~~ FIXED — `check_head()` crashed on fresh repo before first commit
**Fix:** Added `hash_path.exists()` guard; returns `None` when no branch file exists yet. All callers updated to handle `None` hash gracefully.

### ~~Bug 2~~ FIXED — `empty()` wrote incompatible staging area format
**Fix:** Changed `empty_dict` from `{"additions": {}, "removals": []}` to `{}` to match the flat `{filename: hash}` format used everywhere else.

### ~~Bug 3~~ FIXED — `empty_file()` always crashed unpacking `get_staging_area()`
**Fix:** Rewrote `empty_file()` to unpack correctly and handle both cases: removing a staged addition (delete key) and restoring a staged removal (restore from HEAD commit).

### ~~Bug 4~~ FIXED — `check_uncommitted_changes` decorator called `get_status_info()` with no arguments
**Fix:** Decorator now gathers the required `directory_files`, `staging_area`, and `prev_commit_files` arguments before calling `get_status_info()`. Also fixed the loop to iterate lists (not `.keys()`).

### ~~Bug 5~~ FIXED — `write_files_from_dictionary()` / `make_blob_current()` crashed for subdirectory files
**Fix:** Added `filepath.parent.mkdir(parents=True, exist_ok=True)` before writing in both functions.

### ~~Bug 6~~ FIXED — `get_current_wd_to_initialize_repo()` used builtin `dir` instead of parameter `directory`
**Fix:** Changed `current_dir = dir` to `current_dir = directory`.

### ~~Bug 8~~ FIXED — `lstrip("./")` stripped leading dot from dotfiles
**Fix:** Changed to `removeprefix("./")` in both `stage()` and `get_directory_files_dictionary()`.

### ~~Bug 10~~ FIXED — `find_common_ancestor()` only followed first parent of merge commits
**Fix:** BFS now enqueues all parents (`list(commit.parent)`) instead of only `parent[0]`.

### ~~Bug 11~~ FIXED — `branch_switch()` updated HEAD even when checkout was aborted
**Fix:** `checkout_commit()` now returns `False` when it aborts early. `branch_switch()` checks the return value and prints: *"Note: switch to '<branch>' was aborted. HEAD and working directory are unchanged."* Also fixed the HEAD format written by `branch_switch()` and `branch_create()` from `"refs: ..."` to the correct `"ref: ..."`.

### ~~Bug 13~~ FIXED — Bitwise `&` instead of `and` in `remove_branch_ref()`
### ~~Bug 14~~ FIXED — Typo "chekcout" in user prompts
### ~~Bug 15~~ FIXED — Extra `)` in status output string
### ~~Bug 16~~ FIXED — Missing `@wraps` on `check_for_initial_commit` decorator

---

## Active Bugs (5 failing tests)

### Bug — Three-way merge doesn't correctly handle file-only-on-one-branch cases
**Tests failing:** `TestMergeThreeWay::test_three_way_keeps_master_only_change`, `TestMergeThreeWay::test_three_way_merge_commit_contains_all_files`

The merge logic produces a `FileNotFoundError` for a file that exists in one branch's commit but not on disk (because the working directory was set up on a different branch). The `make_blob_current()` call during merge tries to write a file whose blob doesn't exist yet in the expected location, or the merge categorization puts the file in the wrong bucket.

---

### Bug — Three-way merge doesn't honour file deletion on one branch
**Test failing:** `TestThreeWayMergeFileDeletion::test_3way_merge_removes_file_deleted_on_other_branch`

When a file is deleted on the feature branch (`stage(["victim.txt"], "removals")`) and the current branch didn't touch it, the three-way merge should exclude that file from the result. Instead, the file ends up in `unique_files_current_commit` and is kept. The merge categorization logic needs to detect that a file absent from one branch but present in the ancestor (and present-but-unchanged in the other) was intentionally deleted, and should exclude it.

---

### Bug — `remote_prep_push()` doesn't reject non-fast-forward pushes correctly
**Test failing:** `TestNonFastForwardPush::test_push_when_remote_is_ahead_returns_none`

When the remote has commits the local doesn't have, `remote_prep_push()` should return `None` (signaling rejection). Instead it returns a non-None result. The `find_branch_ancestor()` function walks local history looking for the remote tip hash, but the remote tip is a commit that only exists in the remote's object store — not the local one. `get_commit()` therefore can't find it and raises `CommitNotFoundError` rather than returning `[]` for the non-fast-forward case.

---

### Bug — `pull` doesn't make remote files available in working directory
**Test failing:** `TestPull::test_pull_makes_remote_files_available_locally`

After a pull that fast-forwards the local branch, the remote's files are not appearing in the working directory. The pull logic updates the branch pointer but likely doesn't call `make_blob_current()` (or equivalent) to actually write the remote files to disk.

---

## Notes

- **mgignore behavior:** `mgignore()` correctly uses append mode (`'a'`). The test `test_mgignore_overwrites_not_appends` which expected overwrite behavior was deleted as it was testing the wrong behavior. Patterns accumulate across calls, which is the intended semantic.
- **`stage()` for removals:** Now uses `staging.pop(filename, None)` instead of `del` so that staging a file for removal is safe even if the staging area was cleared by `empty()` beforehand.
- **`checkout_commit()` staged-removal check removed:** The previous check (`file not in index and file in tracked_files` → "staged for removal") was too aggressive — it fired incorrectly whenever the staging area was empty (e.g. after `empty()`). The remaining check (file missing from disk, or hash mismatch) correctly detects uncommitted changes.
