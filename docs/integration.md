# postfx-01 Integration

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-05-24

## Purpose

Describe post-FX controller integration with runtime, input, and automation layers.

## Integration Points

- Runs as a system-level post-process stack after effect rendering.
- Exposes slot-trigger API used by hotkeys and automation subsystems.
- Consumed by Auto VJ for cruise/drop/climax impact patterns.

## Input Surface

- Keyboard quick-hit slots via Ctrl+Alt+number bindings.
- Scroll/ctrl-scroll interactions drive continuous hue and rotation passes through core input routing.

## Safety/Compatibility

- App remains functional when drop-in is absent.
- Effects should fail softly and never block render loop progression.

## Related Docs

- ../README.md
- operations.md
- configuration.md
- troubleshooting.md
