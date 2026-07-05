# Frontend Changes: Theme Toggle Button

## Summary
Added a light/dark theme toggle button so the UI is no longer locked to the dark theme. The toggle is a fixed, circular icon button in the top-right corner of the viewport, styled to match the existing send-button aesthetic (rounded, `--surface` background, `--primary-color` hover accent, focus ring).

## Files changed

### `frontend/index.html`
- Added a `<button id="themeToggle">` right after `<body>`, containing two inline SVG icons (sun / moon, Feather-icon style, matching the send button's `stroke="currentColor"` icon convention).
- Button includes `aria-label`, `aria-pressed`, and a `title` attribute for accessibility; label text is updated dynamically by JS to reflect the action the button performs.

### `frontend/style.css`
- Added a `:root[data-theme="light"]` block overriding the dark-theme CSS variables (`--background`, `--surface`, `--surface-hover`, `--text-primary`, `--text-secondary`, `--border-color`, `--assistant-message`, `--shadow`, `--focus-ring`, `--welcome-bg`) with light equivalents. Brand colors (`--primary-color`, `--primary-hover`, `--user-message`, `--welcome-border`) stay constant across themes.
- Added `.theme-toggle` styles: fixed position (top-right), circular button, hover/active/focus-visible states consistent with existing interactive elements (`#sendButton`, `.suggested-item`).
- Icon swap handled in pure CSS: `.theme-icon-moon` hidden by default; `[data-theme="light"]` flips which icon is visible (sun shown in dark mode as an affordance to switch to light, moon shown in light mode to switch back to dark).
- Added subtle `background-color`/`border-color`/`color` transitions to `body`, `.main-content`, and `.sidebar` so the theme switch animates instead of snapping.
- Added a small-screen rule shrinking the toggle button slightly under the existing `768px` breakpoint.

### `frontend/script.js`
- Added `themeToggle` to the cached DOM element references.
- Added `initTheme()`, `applyTheme(theme)`, and `toggleTheme()`:
  - `initTheme()` reads a saved theme from `localStorage` (defaulting to `dark`) and applies it on load, before the welcome message renders.
  - `applyTheme()` sets `data-theme` on `<html>`, updates `aria-pressed`/`aria-label` on the button, and persists the choice to `localStorage`.
  - `toggleTheme()` flips between `dark` and `light` and is wired to the button's `click` event in `setupEventListeners()`.

## Accessibility / keyboard navigation
- The toggle is a native `<button>` element, so it is reachable via Tab and activates on both `Enter` and `Space` without extra JS.
- `aria-pressed` reflects toggle state (`true` = light theme active) for assistive tech.
- `aria-label` updates to describe the action that will happen next ("Switch to light theme" / "Switch to dark theme").
- A visible `:focus-visible` ring (reusing the existing `--focus-ring` variable) shows keyboard focus, matching the focus treatment already used on `#chatInput`, `#sendButton`, and `.suggested-item`.

## Persistence
Theme choice is stored in `localStorage` under the `theme` key and restored on next visit/reload.
