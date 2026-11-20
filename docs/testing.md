# Alpha 2 validation and limitations

Tested release: **ErdOS 1 Alpha 2 (`v1.0.0-alpha.2`)**, November 19, 2026.
The ISO is 1,184,202,752 bytes. SHA-256:

```text
57172a9d911af6c4aa9d1225218d4c066e5edf212f69d51b39629ad05d4a2263
```

## Build and image checks

- Clean Debian 13 live-build, including rebuilt native helpers and standard
  Skippy-XD with physics disabled. The experimental overview dock is absent.
- All 669 internal SHA-256 entries passed. The release verifier compared the
  embedded desktop and installer configuration against the source files,
  checked required packages survive installation, and checked pinned Twig.
- Source syntax, local documentation links, installer policy, public-file
  boundary and release metadata checks passed.
- Regular Mozilla Firefox 160.0.1 is installed. Chromium, Firefox ESR, Snap,
  Node.js, GNOME Shell, tint2 and xterm are absent from the tested system.

## Boot and fresh installation

- BIOS live boot reached the console and launched the desktop after login.
- A fresh UEFI installation completed entirely offline in a disposable KVM VM.
  An account/locale-only test fixture supplied test credentials; the production
  partitioning and erase-confirmation policy remained unchanged.
- The installer presented its disk picker with two disks. The tester selected
  the 24 GiB destination and explicitly accepted the final write confirmation,
  whose initial choice was No. The separate 12 GiB disk remained entirely zero.
- The installed system booted without ISO media and reached a clear tty1 login
  prompt without selecting a boot entry or pressing Enter. Logout from Openbox
  also returned directly to a clear login prompt.
- The installed account successfully used sudo with its own password.
- After adding a virtual network adapter, `apt-get update` succeeded against
  Debian, Debian security/updates and the signed Mozilla repository. Installed
  APT configuration contained no live-media or CD-ROM source.
- Automatic time synchronization was enabled and active. This VM did not report
  an NTP-synchronized clock during the check; successful remote time sync is not
  claimed by this test. Its clock was already correct and APT validation passed.

## Desktop checks

The final BIOS live image and fresh installed image both loaded all twelve
Settings sections, used the dark application theme, and had Firefox, PCManFM
and Twig as the initial browser, folder and text defaults. Super+B opened
regular Firefox; Super+Space displayed the generic default-program menu.
Screenshot creation worked. Background-image tests covered copying an image
into private user configuration, deleting the original and restoring the solid
color. The Network tab correctly disabled Wi-Fi controls when no adapter was
present. The public screenshots were captured from this fresh installation.

Focused development checks also exercised changing and removing default-app
associations, failed launch handling, NetworkManager connection/disconnection
feedback and external-state changes. These simulated Wi-Fi cases and a wired
NetworkManager connection; they are not physical Wi-Fi hardware certification.

## Footprint

Before opening applications or connecting networking, the fresh installation
used **1.80 GiB of disk space** and a median **380.6 MiB of RAM at idle**. The
VM had two CPUs, 2 GiB RAM, a 24 GiB disk and a 1280 × 800 display. Disk counts
used root and EFI filesystem blocks, excluding swap. RAM is
`MemTotal - MemAvailable`, sampled five times ten seconds apart after a two-minute
settle. No packages or APT indexes were added before measuring. The serial test
shell, sampler and read-only fixture mount were included.

[Raw measurements and exact tested ISO](footprint.json).

## Hosted download verification

The same tested image is hosted on [Cloudflare R2](https://downloads.erd.sh/v1.0.0-alpha.2/erdos-amd64.iso). After multipart upload, the entire stored ISO was downloaded back and its SHA-256 matched the value above. Hosting changed; the ISO was not rebuilt.

## Remaining limits

Alpha 2 is experimental. This release check does not certify Secure Boot,
physical Wi-Fi/Bluetooth, touchpad gestures on every device, battery/brightness,
suspend/resume, multi-monitor hotplug or every firmware combination. The new
whole-disk UEFI install test does not certify alongside-OS partitioning or a
fresh BIOS installation. Back up real disks and test hardware before relying on
it. Firefox updates come from Mozilla's signed APT repository; no browser is
bundled as a Snap.

[Historical validation records](history/validation-before-alpha2.md) retain
earlier tests and their limitations.
