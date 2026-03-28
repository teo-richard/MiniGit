# MiniGit Bug Tracker

All confirmed bugs found during adversarial testing, with their status and the test(s) that cover them.

---

## Fixed Bugs

**BUG-1** — `branch_delete()` with a non-existent branch name crashed with `FileNotFoundError`.
`branch_delete()` now catches it and prints a warning instead.
Note: the lower-level `remove_branch_ref()` still raises directly if called without going through `branch_delete()`.
*Tests:* `TestBranchDeleteEdgeCases`

**BUG-2** — `amend()` when HEAD is detached created a bogus `refs/heads/None` file.
*Tests:* `TestAmendDetachedHead`

**BUG-3** — `fetch()` when already up-to-date crashed with `IndexError` on `commits_to_copy[0]`.
Now prints "Already up to date".
*Tests:* `TestFetchEdgeCases::test_fetch_when_up_to_date_does_not_crash`

**BUG-4** — `merge()` with a nonexistent branch raised an unhandled `FileNotFoundError`.
Now prints a user-friendly error message.
*Tests:* `TestMergeEdgeCases::test_merge_nonexistent_branch_prints_error`

**BUG-5** — `remote_prep_push()` when nothing needs pushing silently returned `None` with no feedback.
Now prints "Already up to date".
*Tests:* `TestRemotePushNothingToPush`

**BUG-6** — `revert()` never staged files missing from the target commit for removal, so they were silently carried into the revert commit.
*Tests:* `TestRevertEdgeCases`

**BUG-7** — `pull()` when already up to date crashed with `TypeError` because `fetch()` returned `None` and `merge()` was called unconditionally.
`fetch()` now returns `False` when up to date; `pull()` guards with `if path_to_new_local_branch:`.
*Tests:* `TestPullEdgeCases`

**BUG-8** — `revert()` default message contained the wrong hash because the loop variable was named `hash`, shadowing `commit_hash`.
Renamed to `blob_hash`.
*Tests:* `TestRevertEdgeCases::test_revert_default_message_contains_exact_commit_hash`

**BUG-14** — `mgignore()` opened `.minigitignore` in `"w"` (truncate) mode. A second call silently discarded every pattern added by the first call.
Now uses `"a"` (append) mode.
*Tests:* `TestMgignoreOverwrites`

**BUG-10** — `commit()` never cleared the staging area after a successful commit. Also had a broken import (`from basic_commands import empty` → `from commands.basic_commands import empty`).
Now calls `empty()` at the end of a successful commit.
*Tests:* `TestStagingAreaClearedAfterCommit`

---

## Open Bugs (unfixed)

**BUG-9** — `init(dir)` where `dir` does not yet exist creates the directory then immediately returns, leaving no `.minigit` structure inside it. Also exposed two secondary bugs: config path used a double `.minigit`, and index creation was gated behind `if dir == None`.
*File:* `commands/main_commands.py`
*Tests:* `TestInitNonexistentDir` ✓ FIXED

**BUG-11** — Fast-forward merge calls `make_blob_current()` which only writes files to disk; it never deletes files that were removed on the merged branch. Stale files persist in the working directory.
*File:* `commands/branch_commands.py`
*Tests:* `TestFastForwardMergeFileDeletion` ✓ FIXED

**BUG-12** — Three-way merge classifies files that exist only on one branch as "unique" and always keeps them. A deletion committed on the other branch relative to the common ancestor is silently ignored.
*File:* `commands/branch_commands.py`
*Tests:* `TestThreeWayMergeFileDeletion` ✓ FIXED

**BUG-13** — `stage()` and `get_directory_files_dictionary()` normalise filenames with `str(path).lstrip("./")`, which strips individual characters rather than the substring `"./"`. A filename like `.env` loses its leading dot and is stored as `env`.
*File:* `commands/main_commands.py`, `utils.py`
*Tests:* `TestDotfileNameMangling`

**BUG-15** — `utils.check_staging_area()` iterates `staging_area_removals` with `.keys()`, but removals is a plain `list`, not a `dict`. Raises `AttributeError` whenever there are staged removals.
*File:* `utils.py`
*Tests:* `TestCheckStagingAreaBug`

**BUG-16** — `checkout_commit()` checks whether tracked files are modified but never checks whether the staging area is dirty. Staged additions are silently abandoned; if the user then commits, the blob on disk (post-checkout content) diverges from the hash recorded in the index, corrupting the object store.
*File:* `commands/branch_commands.py`
*Tests:* `TestCheckoutIgnoresStagingArea` ✓ FIXED

**BUG-17** — `find_common_ancestor()` only ever follows `parent[0]` when building the ancestor set and walking history. In a repo that already contains a merge commit, it misses the second-parent branch and returns an ancestor that is older than the true common ancestor.
*File:* `utils.py`
*Tests:* `TestFindCommonAncestorMergeHistory`

**BUG-18** — `revert()` to the initial commit (which has `files={}`) should produce a commit with no files. Instead, files from the parent commit are silently carried forward because `revert()` stages the additions from the target commit but never stages the files that need to be removed.
*File:* `commands/history_commands.py`
*Tests:* `TestRevertEdgeCases::test_revert_to_initial_commit_yields_empty_files` *(currently fails)*
