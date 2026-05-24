# postfx-01 Operations

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-05-24

## Purpose

Operational runbook for the global post-FX controller.

## Live Trigger Surface

Quick-hit slots:

- `Ctrl+Alt+1` to `Ctrl+Alt+8` from README
- Current controller also supports slot 9 and 10 internally (`Ctrl+Alt+9`, `Ctrl+Alt+0` help entries)

## Runtime Behavior

- Slot effects are one-shot bursts with per-slot duration.
- Scroll-driven hue-shift and scene-rotation passes can run independently.
- Active pass order is slot effect -> hue shift -> scene rotation.

## Operator Guidance

- Keep quick-hit durations short to preserve scene readability.
- Use slot families consistently per show segment for visual identity.
- Clear continuous scroll FX between songs/sections when needed.

## Related Docs

- ../README.md
- configuration.md
- integration.md
- troubleshooting.md
