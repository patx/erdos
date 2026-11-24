# ErdOS build and test storage policy

- Use `./build.sh` on Debian 13 or `./scripts/build-in-docker.sh` for ISO builds.
  Both own their temporary workspace and clean it on success, failure or normal
  interruption. `--prepare` is a staging check and does not retain its files.
- Run local runtime/VM tests through `./scripts/run-test.sh COMMAND ...` and put
  every disposable VM disk, extraction and capture under `$ERDOS_TEST_DIR`.
  Test stdout/stderr is saved in a bounded latest-test log; print small results
  there and copy accepted benchmark data into `docs/footprint.json` before exit.
- Use `./scripts/run-in-debian.sh [--privileged] COMMAND ...` when a disposable
  Debian container is needed. Use `--privileged` only for mount/KVM tests that
  need it. `/project` is read-only, `/artifacts` is the disposable test workspace.
- Do not create persistent ErdOS build/test containers or put VM disks/extracted
  systems in unmanaged container `/tmp`, Downloads, or other project folders.
  The wrappers remove their own containers, including temporary compiler/APT data.
- Keep only `dist/erdos-amd64.iso` and its checksum as normal local build outputs.
  Successful publication removes older top-level ErdOS ISO names and stale
  standard release companions. Failed builds preserve the last verified ISO.
  Release packaging is explicit and may temporarily create companion artifacts.
- Never run a global Docker prune or delete other containers, images, caches,
  Downloads or unrelated projects as part of ErdOS cleanup. Shared Debian base
  images remain cached; build/test containers do not.
- Keep logs bounded under ignored `logs/`; do not retain large failed build
  trees as the default debugging method. If active processes/mounts or an
  unavailable Docker daemon prevent safe cleanup, report the exact workspace
  instead of deleting through mounts or concealing the failure.
- Follow `docs/upstream-labwc.md` for compositor changes. No runtime packages or
  compositor versions need changing for build/test storage maintenance.
