const gallery = document.querySelector('#screenshots');
const dialog = document.querySelector('#screenshot-preview');
const imageContainer = dialog.querySelector('.screenshot-dialog-image');
let opener;

if (typeof dialog.showModal === 'function') {
  gallery.querySelectorAll('a').forEach(link => link.setAttribute('aria-haspopup', 'dialog'));

  gallery.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 ||
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    const link = event.target.closest('a');
    if (!link) return;

    event.preventDefault();
    opener = link;
    const preview = link.querySelector('img').cloneNode();
    preview.removeAttribute('fetchpriority');
    preview.src = link.href;
    imageContainer.replaceChildren(preview);
    dialog.showModal();
  });

  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });

  dialog.addEventListener('close', () => {
    opener.focus({ preventScroll: true });
  });
}
