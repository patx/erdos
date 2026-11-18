'use strict';

const scene = document.querySelector('.desktop-scene');
const demoButtons = [...document.querySelectorAll('[data-demo]')];
const views = {
  overview: {
    key: 'Super', hint: 'Everything in view.',
    description: 'Tap Super for Skippy’s window overview. Pick a window. Keep going.',
    label: 'Illustration of Exposé showing Sakura, Chromium and Twig windows side by side',
  },
  menu: {
    key: 'Super + Space', hint: 'Everything within reach.',
    description: 'Your apps and settings, right here. Right-click the desktop works, too.',
    label: 'Illustration of the Openbox right-click menu over three open windows',
  },
  workspaces: {
    key: 'Super + Shift + O', hint: 'An overview of your workspaces.',
    description: 'Dynamic workspaces keep one spare. Use it, and another appears.',
    label: 'Illustration of two workspaces: one with windows, one empty and ready to use',
  },
};
let introTimer;
function showDemo(name) {
  clearTimeout(introTimer);
  const view = views[name];
  if (!scene || !view) return;
  scene.dataset.view = name;
  scene.setAttribute('aria-label', view.label);
  document.querySelector('#scene-key').textContent = view.key;
  document.querySelector('#scene-hint').textContent = view.hint;
  document.querySelector('#demo-description').textContent = view.description;
  demoButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.demo === name)));
}
demoButtons.forEach(button => button.addEventListener('click', () => showDemo(button.dataset.demo)));
// A single opening demonstration; nothing loops or captures OS shortcuts.
if (scene && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
  scene.dataset.view = 'desktop';
  introTimer = setTimeout(() => showDemo('overview'), 1000);
}
