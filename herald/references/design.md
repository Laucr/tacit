# Design Notes

Herald renders reports in the **nothing-design** language used by the vibes project. The full canonical rule lives at `/data/codes/Apps/vibes/.claude/rules/nothing-design.md`; this file captures the parts herald has to honour and the choices it makes given that it can't take a runtime dependency on `@vibes/nothing-ui`.

## Principles inherited from nothing-design

Herald's CSS is hand-written but token-named so it stays recognisable as part of the same family.

1. **Dark default, OLED-friendly.** `--nd-black: #000` background, `--nd-text-display: #fff` headings, `--nd-text-primary: #e8e8e8` body. Light mode is opt-in via `data-theme="light"` on the `<html>` element — the toggle isn't shipped (no theme widget by default), but a user can swap by hand.
2. **Three-layer hierarchy per page.** Title > section heading > label/metadata. The title is the only display-weight element. Section headings stay at heading scale. Labels and metadata are Fira Code ALL CAPS with `letter-spacing: 0.08em`.
3. **Two font families, max.** Space Grotesk (body) and Fira Code (mono / labels). System fallbacks keep the file lean.
4. **One accent moment per page.** The verdict pill (or severity pill, for drift) is the single use of `--nd-accent`. Status cells inside tables use the dedicated `--nd-success / --nd-warning / --nd-error / --nd-info` palette and are not considered "accent moments".
5. **Bracketed status pills.** All inline status uses the `[ TEXT ]` pattern with brackets in `--nd-text-secondary` and the value in the appropriate status colour. No filled badges, no rounded chips with backgrounds.
6. **Flat surfaces.** Card-style containers use `--nd-surface` with a 1px `--nd-border` outline. No drop shadows, no gradients, no inner glow.
7. **No zebra striping.** Hover rows shift to `--nd-surface-raised`. Separator lines between rows are 1px `--nd-border`.
8. **No emoji as UI.** Text-only.
9. **Subtle motion only.** `cubic-bezier(0.25, 0.1, 0.25, 1)` ease, 150–250ms. Used for the bundle-mode left-rail item hover; nothing else.

## Why not embed `@vibes/nothing-ui` directly

The package is a React library and ships its CSS as a separate `dist/styles.css`. Embedding the React components would force herald to spawn a build step and emit JS bundles — the goal here is **one HTML file, no toolchain**, openable on any browser, including ones in jump boxes and corporate sandboxes that block remote font/CSS fetches. Herald instead inlines the equivalent CSS directly, keyed off the same token names. When `@vibes/nothing-ui` updates a token, herald should be updated to match.

The token names (`--nd-black`, `--nd-success`, `--nd-size-display-md`, `--nd-tracking-label`, etc.) are kept identical to the package so a future maintainer can `diff` the two stylesheets and see what's drifted.

## Why pure HTML, no JS

Single-report mode emits a fully static HTML document — no script tag at all. Bundle mode includes a tiny vanilla-JS switcher (~30 lines) that swaps between report payloads embedded as `<template>` tags. There's no dependency on a framework or runtime. This means:

- The file works in any browser that understands HTML5 + CSS3 (every browser made in the last decade).
- It works offline.
- Email clients that strip JS still render the single-report form correctly.
- A user can `cat` the file and grep it.

## Why system-font fallback instead of embedded fonts

Embedding the four nothing-design weights of Space Grotesk + Fira Code would add ~80–100KB to every report. The fallback chain (Space Grotesk → DM Sans → system-ui; Fira Code → JetBrains Mono → ui-monospace) preserves the **shape** of the typography (geometric sans for body, mono for labels) on machines that have either of the preferred families installed; on machines that don't, system-ui still hits the same hierarchy targets. Reports are read-once, share-many — the size matters.

If a user really wants the proper fonts (e.g. shipping a report to a public reader), they can serve it from a vibes app and the gateway will provide the fonts via `/assets/nothing/styles.css`. Herald's job is the portable artifact.

## Light mode

The token table for light mode is included in the inline CSS (under `[data-theme="light"]`). To switch a rendered file, edit the opening tag to `<html lang="en" data-theme="light">`. This is intentionally a manual step — the default product is dark, and adding a UI toggle to a static report would violate the "no theme-toggle widget without product reason" rule from `nothing-design.md`.
