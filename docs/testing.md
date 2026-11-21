# Development validation

This checkout and its local ISO are the current development version, ahead of
published Alpha 2. The published release remains available on the download site;
it is not replaced by a local build.

## Source and interaction checks

- Source syntax, local links, installer policy and public-file boundary checked.
- Native helpers compile on Debian 13, including touchpad-only button remapping.
- In an isolated real Openbox session, Super + right-click opens the root menu
  over application windows. Both new menu triggers toggle independently, while
  desktop right-click and Super + Space continue to work.
- An isolated XInput fixture confirms touchpad middle-click remaps and restores
  without changing a separate mouse's button mapping. Physical touchpad testing
  is still required.
- The Menu tab renders both controls. Startup saves reject invalid shell syntax
  and conflicting external edits, keep a previous-version backup and do not
  execute commands while saving.
- Custom power controls were dropped. The image retains Debian's power defaults
  and adds no power-management packages, timers or services.

## Current image checks

The November 20, 2026 development build passed final ISO verification against
the current desktop configuration, embedded installer policy, required installed
packages, vendored Twig and Skippy's recorded source/binary provenance with
physics disabled. All 669 embedded file checksums passed. The exact
local image size and SHA-256 are recorded in [release.json](release.json).

The current development image still needs a fresh boot/install and physical
hardware test. Earlier release test results are preserved in tagged Git history;
they do not certify this development build. Footprint figures on the website are
from the published Alpha 2 measurement, not a new development measurement.
