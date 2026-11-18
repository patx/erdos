'use strict';

async function showRelease() {
  if (!document.querySelector('#release-download')) return;
  try {
    const response = await fetch('release.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Release metadata unavailable');
    const release = await response.json();
    if (!/^[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(release.repository) ||
        !/^[a-f0-9]{64}$/.test(release.iso.sha256) ||
        !Number.isSafeInteger(release.iso.bytes) || release.iso.bytes < 1) {
      throw new Error('Invalid release metadata');
    }
    const repository = `https://github.com/${release.repository}`;
    const download = document.querySelector('#release-download');
    const date = new Date(`${release.date}T12:00:00Z`);
    document.querySelector('#release-date').textContent = new Intl.DateTimeFormat('en', {
      dateStyle: 'long', timeZone: 'UTC',
    }).format(date);
    document.querySelector('#release-size').textContent =
      `${(release.iso.bytes / 2 ** 30).toFixed(2)} GiB (${release.iso.bytes.toLocaleString('en')} bytes)`;
    document.querySelector('#release-checksum').textContent = release.iso.sha256;
    document.querySelector('#checksum-details').hidden = false;
    if (release.published === true && typeof release.tag === 'string' && release.tag.length > 0) {
      download.href = `${repository}/releases/download/${encodeURIComponent(release.tag)}/${encodeURIComponent(release.iso.filename)}`;
      download.textContent = 'Download amd64 ISO ↓';
      document.querySelector('#release-status').textContent =
        `${release.status} · ${release.tag} · amd64`;
    } else {
      download.href = `${repository}/releases`;
    }
  } catch {
    // The ordinary releases link remains usable if release metadata is unavailable.
    document.querySelector('#release-status').textContent =
      'See GitHub Releases for download availability, build details and checksums.';
  }
}

const copyButton = document.querySelector('#copy-checksum');
if (copyButton) {
  copyButton.addEventListener('click', async () => {
    const checksum = document.querySelector('#release-checksum');
    const status = document.querySelector('#copy-status');
    try {
      await navigator.clipboard.writeText(checksum.textContent);
      status.textContent = 'Checksum copied.';
    } catch {
      const range = document.createRange();
      range.selectNodeContents(checksum);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = 'Checksum selected. Use your browser’s copy command.';
    }
  });
}

showRelease();
