# postfx-01 Configuration

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-05-24

## Purpose

Reference for post-FX controller timing and continuous-pass settings.

## Core Keys

```toml
[postfx]
enabled = true
hit_duration = 0.9
active_slot = 0
hue_shift_timeout_s = 3.0
hue_shift_step = 0.0277778
rotation_timeout_s = 3.0
rotation_step_rad = 0.07
```

## Per-Slot Duration Keys

- `slot1_duration` ... `slot10_duration`

Use slot-specific durations to control burst feel without changing global defaults.

## Notes

- Continuous passes (hue/rotation) are independent from burst slot timing.
- Disable the subsystem globally with `enabled = false` if needed for troubleshooting.

## Related Docs

- ../README.md
- operations.md
- integration.md
- troubleshooting.md
