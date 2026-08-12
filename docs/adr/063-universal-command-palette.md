# ADR 063 — Universal Command Palette

## Status

Accepted.

## Context

The brainstorm incorporated into the roadmap (Sprint 0.7) called for a Cmd+K-style Universal Command Palette so users don't have to leave whatever screen they're on to jump somewhere else. `GET /api/v1/search` already covers every substantial record type (ADR 062), and the existing `GlobalSearchScreen` proved the aggregator's UI pattern (icon per module, debounced query, tap-to-navigate). What was missing was a lightweight, keyboard-reachable entry point that doesn't require a full route push — a dialog overlay reachable from anywhere in the app, not just a destination you navigate to.

## Decision

Add `CommandPaletteDialog` (`apps/mobile/lib/src/widgets/command_palette_dialog.dart`), a `Dialog` opened via `showDialog` that reuses the existing `SearchService`/`SirisSearchResult` types unchanged. It adds keyboard-first interaction on top of the same click-to-navigate pattern: arrow-key highlight movement, Enter opens the highlighted result, Escape closes, and clicking/tapping a result works exactly like `GlobalSearchScreen` (pop the dialog, call `onOpenTarget`).

Wire a global `Cmd+K`/`Ctrl+K` shortcut in `AppShell` via `HardwareKeyboard.instance.addHandler`, not `CallbackShortcuts`/`Focus.onKeyEvent`. The Focus-based approach was tried first and silently failed to fire at all when nothing in the widget subtree held keyboard focus — a real gap, not a testing artifact, since `CallbackShortcuts` only intercepts key events that bubble up from a focused descendant. `HardwareKeyboard.instance.addHandler` registers a true global pre-filter that runs regardless of focus state, which is what an app-wide shortcut actually needs. The same problem showed up a second time inside the dialog itself: wrapping the results list in an ancestor `Focus.onKeyEvent` never received ArrowUp/ArrowDown, because the focused `TextField`'s own `EditableText` consumes vertical arrow keys internally (cursor-movement semantics) before they can bubble. `CommandPaletteDialog` uses the same `HardwareKeyboard` global-handler pattern for its own arrow/Escape handling, sidestepping focus-bubbling entirely.

The desktop sidebar's existing "Search" entry now opens the palette (with a `⌘K` hint) instead of pushing `GlobalSearchScreen`. The full-screen search page stays reachable from the mobile Quick Actions sheet, where a modal dialog is a worse fit than a dedicated screen with larger touch targets.

## Consequences

- Any screen in the app is one keyboard shortcut away from searching and jumping to Knowledge, Projects, Engineering, Standards, Siris Memory, Docker, running, gym or activity — no navigation required first.
- No new backend surface: the palette is purely a second UI on top of the search endpoint ADR 062 already built for exactly this reuse.
- The `HardwareKeyboard.instance.addHandler` pattern established here is the correct one for any future app-wide keyboard shortcut — `CallbackShortcuts`/`Focus.onKeyEvent` should be reserved for shortcuts scoped to a widget that's guaranteed to hold focus (e.g. within a form), not global ones.
- `GlobalSearchScreen` remains the mobile/touch-first entry point; the palette is additive, not a replacement.
