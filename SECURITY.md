# Security

ErdOS is an experimental Debian-derived live image. It does not provide a separate
security team or promise a security-update schedule. Installed systems use Debian
Trixie’s security and update repositories; maintainers must rebuild live images
to incorporate package updates. The live account (`user` / `live`) is public and
has administrative access. It is not a private or hardened account.

## Reporting an ErdOS vulnerability

Use the repository’s private **Report a vulnerability** option under Security,
if enabled: <https://github.com/patx/erdos/security/advisories/new>.
If private reporting is unavailable, open an issue asking for a private reporting
channel without posting exploit details or credentials. Do not include real disk
contents, passwords, Wi-Fi keys or authentication tokens in reports.

Report vulnerabilities in Debian packages through Debian’s security-reporting
process: <https://www.debian.org/security/>. An ErdOS report should identify the
ISO checksum, affected component, impact and a safe reproduction using a VM.

## Trust and installation

SHA256 checksums detect corruption; unsigned checksums do not authenticate a
publisher. Obtain images and checksums from the same intended GitHub release and
verify them before booting. Secure Boot is disabled in this project. Review the
installer’s destination disk and write confirmation before installing.
