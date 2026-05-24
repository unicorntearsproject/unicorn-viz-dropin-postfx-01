# postfx-01 Troubleshooting

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-05-24

## Purpose

Troubleshooting guide for post-FX trigger and rendering behavior.

## Common Issues

### Slot hotkeys do nothing

- Confirm `[postfx] enabled = true`.
- Confirm help overlay shows Post FX entries.
- Verify active slot bindings are not shadowed by custom key handling.

### Effect feels too long or too short

- Tune `slotN_duration` for the specific slot.
- Keep `hit_duration` as baseline and override only outliers.

### Hue/rotation gets stuck

- Use clear commands or allow timeout to expire.
- Reduce `hue_shift_timeout_s` / `rotation_timeout_s` for tighter live control.

### Performance drops on heavy scenes

- Reduce simultaneous high-cost slot usage.
- Lower render resolution scale during aggressive post-FX segments.

## Related Docs

- ../README.md
- operations.md
- configuration.md
- integration.md
