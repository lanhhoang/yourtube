# Design

Tokens live in `apps/web/src/app.css` (Tailwind 4 `@theme`, dark set on `.dark`). This file is the contract; change both together.

## Direction

A minimal, near-black YouTube: the layout grammar (top bar, left rail, chips, thumbnail grid) with nothing else. Surfaces are flat and monochrome so thumbnails carry the colour. Red is the only accent. Dark is the default theme; light and system are options. Computer only, designed at 1280 and 1440 px wide, no narrower than 960 px.

Chosen by the owner on 2026-11-15 from the approved mockups (`direction-v2.html`, `playlist-quality.html`): mockup colour values kept, Inter as the one typeface.

## Colour

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#0b0b0c` | `#ffffff` | page |
| `surface` | `#161618` | `#f4f4f5` | inputs, panels |
| `raised` | `#1f1f22` | `#e9e9eb` | chips, rail icon tiles, hover |
| `line` | `#2a2a2d` | `#dcdce0` | decorative hairlines only |
| `line-strong` | `#76767d` | `#85858d` | borders of controls (3:1 UI contrast) |
| `fg` | `#f1f1f1` | `#0f0f10` | text |
| `muted` | `#8d8d8d` | `#5f5f66` | meta text |
| `accent` | `#ff0033` | `#d90029` | red as text, bars, selection marker |
| `accent-fill` | `#e6002e` | `#d90029` | red behind white text (count badges, custom badge) |
| `warn` | `#f5a524` | `#8a5200` | amber: "below your cap" only |
| `danger` | `#ff6b6b` | `#c4161c` | failures |
| `action` / `on-action` | `#f1f1f1` / `#0b0b0c` | `#0f0f10` / `#ffffff` | primary button, selected chip |

Contrast (WCAG, measured 2026-11-15): dark `fg` 17.4, `muted` 5.4–5.9, `accent` 4.6–5.0, `warn` 8.9–9.6, `danger` 6.5–7.1, white on `accent-fill` 4.8; light `fg` 19.2, `muted` 5.8–6.3, `accent` 4.8–5.3, `warn` 5.8–6.4, `danger` 5.5–6.0. White on `#ff0033` is 3.96 and is never used for text. Status is never colour alone: badges carry text.

Rules: red marks progress bars, the selected format, rail counts and custom-override badges, and nothing else. The logo mark and favicon are fixed brand artwork in their own reds (`#ff0000` mark, `#dd2222`/`#bb1a1a` favicon). They are the same in both themes and are not tokens. No gradients on UI, no glow, no coloured side borders. Elevation is a flat surface step; no shadows except menus (offset 0 8px, blur 24px, 40% black).

## Typography

Inter Variable (`@fontsource-variable/inter`), bundled; nothing loads from a CDN. Numerals are tabular wherever progress, sizes or durations change.

| Step | Size | Weight | Use |
|---|---|---|---|
| `xs` | 12 px | 500 | badges, durations, rail labels |
| `sm` | 13 px | 400–500 | meta lines, table cells |
| `base` | 15 px | 400–600 | body, titles in cards |
| `lg` | 17 px | 600 | section headings |
| `xl` | 22 px | 700 | page and video titles |

Tracking: 0 for body, -0.01em for `xl`. Body measure under 70ch.

## Spacing, shape, motion

- Spacing scale is Tailwind's 4 px grid; groups 8–12 px, grid gaps 16 px × 24 px, page padding 24 px.
- Radii: controls 8 px, thumbnails 8 px, chips 8 px, pills (URL field, buttons, segmented control) fully round. No card is nested in a card.
- Motion: one idea, state changes ease out in 120–200 ms (`cubic-bezier(0.16, 1, 0.3, 1)`); progress bars animate width only. `prefers-reduced-motion` removes it.
- Focus: 2 px `fg` outline with 2 px offset on every interactive element. Text selection and caret use the accent.

## Layout

Top bar 56 px: wordmark (player mark, 20 px tall, + "yourtube"), pill URL field centred up to 560 px, Fetch button, options menu. Left rail 72 px: icon over 11 px label, red count on Queue; theme tile in the rail footer (moon/sun/monitor, cycles Dark → Light → System; Settings keeps the three-option control). Content scrolls under the bar.
