# Phone layout mockups (390×844)

Source: `docs/design/phone-mockups.html` (all screens, dark row then light row, `DESIGN.md` tokens). Status: **approved by the owner on 2026-11-18**.

## Shell
Top bar pads the status bar (`safe-area-inset-top`), shows the mark only, a 44 px-tall field (16 px text so iOS doesn't zoom), Paste (empty field), Fetch and options at 44 px. A bottom tab bar (Library, Queue with red count in text, Settings) pads the home indicator. Toasts sit at the top, full width, below the status bar.

## Library
Single-column list: thumbnail left (40%), title/meta right. Search on its own row, chips 44 px tall and scrollable inside their row. Tap opens Watch. The hover-only card menu is dropped on phones (Watch has Save and Delete).

## Queue
Rows with a smaller thumbnail; Cancel/Retry/Dismiss 44 px under each row.

## Fetch video and playlist
One column. "Add to queue" 44 px. Playlist: two-up grid, select checkbox with a 44 px hit area (visible box stays small).

## Override bottom sheet
Docked to the bottom, max 85% height, scrolls inside, one title and one Close button (44 px), backdrop tap and Escape close it.

## Settings
Stacked form, 44 px inputs and buttons. Theme radios live here (no rail tile). A placeholder row for Phase 7's notification toggle.

## Watch
Full-bleed player, Save and Delete 44 px side by side in thumb reach.

## Owner decisions
- Library card menu dropped on phones: approved
- Top bar under the status bar, 16 px field: approved
- Sheet has one title/Close (panel header hidden in sheet mode): approved
- Playlist checkbox 44 px hit area: approved
- Overall approval: approved
