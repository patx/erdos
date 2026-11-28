# Maintaining the ErdOS labwc fork

The maintenance fork is [patx/labwc-erdos](https://gitman.io/patx/labwc-erdos).
Gitman does not need its own copy of the upstream project first: this repository
was created by cloning GitHub's original Git history, adding our commits, and
pushing selected branches to the empty Gitman repository. It is an independent
Git repository with a shared ancestor, not a Gitman web-UI fork relationship.

The upstream base remains **labwc 0.9.7**, commit
`f0dbad27fcf6e388cad1aa32448a1d548da68990`. **wlroots remains 0.19.2**.
Establishing this workflow did not upgrade either project or change a byte of
ErdOS's vendored compositor source. The existing development ISO and benchmark
results remain valid; no ISO rebuild is needed for this maintenance setup.

## Branches and source pin

| Ref | Purpose |
| --- | --- |
| Gitman `main` | Maintained ErdOS branch, including upstream history |
| Gitman `upstream-base` | Clean upstream commit currently incorporated |
| `erdos-0.9.7-1` | Initial preserved ErdOS snapshot tag |
| Local `upstream/*` | GitHub remote-tracking refs; fetching does not change our branch |

[labwc-fork.json](../vendor/labwc-fork.json) records the exact upstream and fork
commits, snapshot ref, repository locations and vendored tree hash. Commits,
not moving branch names, determine the build source. The fork preserves original
authors and licenses. Its seven feature commits cover:

1. Session policy/action bridge and persistent overview state.
2. Alternative shortcut keys and mouse contexts.
3. Native gestures, Super activation, touchpad menu and action dispatch.
4. Dynamic workspace maintenance from window lifecycle events.
5. One-shot automatic layout dispatch after output hotplug.
6. Live overview previews and cached blurred backdrop.
7. On-open menu clock and battery status.

A final documentation commit adds `ERDOS.md`. These commits reconstruct the
current feature set; they are not a promise that every intermediate state is a
release candidate. Validate the complete series before shipping it.

## One-time local setup

Run outside the ErdOS checkout:

```sh
git clone https://gitman.io/git/patx/labwc-erdos erdos-labwc
cd erdos-labwc
git remote add upstream https://github.com/labwc/labwc.git
git remote set-url --push upstream DISABLED
git config remote.pushDefault origin
git fetch origin upstream-base
git branch --track upstream-base origin/upstream-base
```

Here `origin` is **Gitman**, and `upstream` is **GitHub**. Git remote configuration
is local and is not inherited by later clones, so repeat these steps for each
maintenance checkout. The disabled upstream push URL guards against accidental
GitHub pushes. Do not use `git push --mirror`, `--all` or `--tags` to synchronize
this fork: push only reviewed branches and our selected snapshot tags.

## Normal ErdOS feature changes

Develop compositor changes in the fork first, on a topic branch from `main`.
Keep commits scoped to a feature or fix, with any necessary header/build hooks
in the same commit. Build and exercise the complete candidate. Merge accepted
work into the maintained `main`, tag the tested snapshot, then import that exact
commit into ErdOS using the procedure below. Application configuration and
Settings remain in the main ErdOS repository.

If code was edited directly in `vendor/labwc`, move those edits to focused fork
commits before importing. The sync helper refuses to overwrite vendor files that
differ from the currently recorded fork. After saving those changes as fork commits, import from a clean ErdOS review
checkout containing the old pinned snapshot. Do not
bypass the guard by deleting files or changing the pin hash just to make it pass.

## Check the current snapshot

From the ErdOS checkout, with the maintenance clone beside it:

```sh
python3 scripts/sync-labwc.py --checkout ../erdos-labwc --check
python3 scripts/check-project.py
```

The first command reads the pinned commit using `git archive`, compares all
retained files, checks upstream ancestry/version and verifies the tree hash.
It does not fetch, check out a branch, edit files, push or upgrade anything.
The normal source/CI check verifies the recorded vendor hash offline. Normal ISO
builds still use the vendored files: no new runtime dependency, submodule or
network clone is introduced.

## Deliberately update an upstream version later

Do not run this section merely to refresh remote information. Fetching is safe;
merging/importing is the explicit upgrade step. Choose a stable release after
reviewing its release notes, dependency requirements and relevant security fixes.

In the fork:

```sh
git switch main
git pull --ff-only origin main
git fetch upstream --tags
git switch -c update/labwc-X.Y.Z
git merge --no-ff <selected-upstream-release-tag>
```

Replace placeholders with the chosen upstream release; these are not runnable
commands as written. Resolve conflicts by understanding both changes. Do not
resolve the whole merge using `ours`/`theirs`, copy a new upstream tree over our
branch, or rebase/force-push published `main`. If the candidate is wrong, abort
an unfinished merge with `git merge --abort`; use a review branch to keep the
maintained branch intact. A clean merge is not proof that behavior is unchanged.

Check whether the selected labwc version needs a different wlroots release.
Review and pin a compatible wlroots update separately if required; do not follow
wlroots's development branch automatically. Our build statically links the
pinned wlroots library, so Debian package upgrades do not update that copy.

Use an isolated ErdOS review checkout and the explicit import procedure below
to build/test the candidate with pinned dependencies. This keeps the maintained
ErdOS checkout intact while reviewing a candidate. After acceptance, merge
the review branch into `main` without rewriting published history. Move the
clean `upstream-base` branch forward to the selected upstream commit and create
an ErdOS snapshot tag. Push only `main`, `upstream-base` and that tag to `origin`.
A non-fast-forward rejection needs investigation, not a force push.

## Import an accepted fork commit into ErdOS

Start with a clean ErdOS checkout and a clean fork working tree. Both the old
pinned fork commit and the new candidate must be available in local history. Use an exact
upstream commit and the corresponding upstream version, even for an ErdOS-only
change where those two values remain unchanged:

```sh
python3 scripts/sync-labwc.py --checkout ../erdos-labwc --import \
  --ref <tested-ErdOS-snapshot-tag-or-commit> \
  --base <exact-40-character-upstream-commit> --version <upstream-version>
git diff --stat
git diff -- vendor/labwc-fork.json vendor/labwc/UPSTREAM
python3 scripts/sync-labwc.py --checkout ../erdos-labwc --check
python3 scripts/check-project.py
```

The helper exports committed files only, updates the pin and `UPSTREAM`
version/commit fields, and preserves the ErdOS-specific provenance note. It omits
upstream `.github/`, files named `.gitignore`, and fork-only `ERDOS.md`, matching
the existing vendor boundary. It rejects symlinks/unsafe archive entries and
refuses an import over unreconciled runtime changes. It stages a replacement
before swapping directories and restores the previous tree if the pin write
fails. Git provides review/reversion after a successful import. No build, fetch,
push or publication happens inside the helper.

If the upstream version changes, also review compiler prerequisites,
`build-helpers.sh` version records, Meson wlroots ABI names/options, notices and
`THIRD_PARTY.md`. The build helper currently records labwc 0.9.7/wlroots 0.19.2
explicitly. The import helper updates the source pin; it is not an automatic
dependency or build-system migration.

Review the full diff, not just the metadata shown above. Commit the imported
source, pin and related changes together only after validation. This keeps each
ErdOS revision tied to a specific tested fork snapshot.

## Validation and delivery

Follow [building.md](https://patx.gitman.io/erdos/building.md) and [testing.md](https://patx.gitman.io/erdos/testing.md). For a compositor
update, cover overview previews/selection/dismissal, native gestures, Super and
other shortcuts, dynamic workspaces, menu status and Settings integration,
display modes/hotplug, XWayland, suspend/resume on supported hardware, and a fresh
offline install. Remeasure installed disk and idle RAM using the documented VM
method. Headless checks complement physical hardware tests.

Git history/import alone does not add runtime disk or RAM overhead. New upstream
features and dependencies can, so review them before accepting a version.

The compositor is an ErdOS-built `/usr/bin/labwc` in `erdos-labwc`, rather
than Debian's labwc package. Deliver tested compositor changes through the signed
APT repository described in [updates.md](https://patx.gitman.io/erdos/updates.md), together with matching
corresponding source. Increment the package version before publication; do not
restart an active user session during installation. Rebuilding an ISO alone does
not update existing installations. The old hosted Alpha 3 Settings bundle does
not deliver compositor binaries. Keep known-good source and images available.
