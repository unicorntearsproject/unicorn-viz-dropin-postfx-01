"""System-level post-process stack controller drop-in.

Loads post-process effects from effects/ and applies one active effect globally.
"""
from __future__ import annotations

import logging
import importlib.util
import sys
from pathlib import Path
from typing import Any

import moderngl

_EFFECTS_DIR = Path(__file__).resolve().parent / 'effects'


def _load_effect_class(module_filename: str, class_name: str) -> type:
    """Load one post-fx effect class from effects/ using isolated module names."""
    path = _EFFECTS_DIR / module_filename
    spec = importlib.util.spec_from_file_location(
        f'postfx_effect_{path.stem}_{abs(hash(str(path)))}',
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f'PostFX: failed to load {path}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = getattr(mod, class_name, None)
    if cls is None:
        raise ImportError(f'PostFX: {class_name} missing in {path}')
    return cls


_BASE_SPEC = importlib.util.spec_from_file_location(
    'postfx_effects_base',
    _EFFECTS_DIR / 'base.py',
)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise ImportError(f'PostFX: failed to load {_EFFECTS_DIR / "base.py"}')
_BASE_MOD = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules['postfx_effects_base'] = _BASE_MOD
_BASE_SPEC.loader.exec_module(_BASE_MOD)

ChromaticAberration = _load_effect_class('chromatic_aberration.py', 'ChromaticAberration')
FilmGrainDither = _load_effect_class('film_grain_dither.py', 'FilmGrainDither')
GlitchSlices = _load_effect_class('glitch_slices.py', 'GlitchSlices')
HeatHazeRefraction = _load_effect_class('heat_haze_refraction.py', 'HeatHazeRefraction')
HueShift = _load_effect_class('hue_shift.py', 'HueShift')
LensDistortionVignette = _load_effect_class('lens_distortion_vignette.py', 'LensDistortionVignette')
MultiPassBloom = _load_effect_class('multi_pass_bloom.py', 'MultiPassBloom')
RadialZoomBlur = _load_effect_class('radial_zoom_blur.py', 'RadialZoomBlur')
SceneRotation = _load_effect_class('scene_rotation.py', 'SceneRotation')
SmokeBubbles = _load_effect_class('smoke_bubbles.py', 'SmokeBubbles')
TimeScrambleWarp = _load_effect_class('time_scramble_warp.py', 'TimeScrambleWarp')
TemporalFeedbackTrail = _load_effect_class('temporal_feedback.py', 'TemporalFeedbackTrail')

log = logging.getLogger(__name__)


DROPIN_CAPABILITIES = {
    'name': 'postfx',
    'class_symbol': 'PostFxController',
    'key_handler_attr': 'handle_key',
}


HELP_ENTRIES = [
    ('Post FX', 'Ctrl+Alt+1', 'Chromatic Aberration'),
    ('Post FX', 'Ctrl+Alt+2', 'Film Grain + Dither'),
    ('Post FX', 'Ctrl+Alt+3', 'Glitch Slices'),
    ('Post FX', 'Ctrl+Alt+4', 'Heat Haze Refraction'),
    ('Post FX', 'Ctrl+Alt+5', 'Lens Distortion + Vignette'),
    ('Post FX', 'Ctrl+Alt+6', 'Multi-pass Bloom'),
    ('Post FX', 'Ctrl+Alt+7', 'Radial Zoom Blur'),
    ('Post FX', 'Ctrl+Alt+8', 'Temporal Feedback Trail'),
    ('Post FX', 'Ctrl+Alt+9', 'Time Scramble Warp'),
    ('Post FX', 'Ctrl+Alt+0', 'Smoke & Bubbles (club fog)'),
    ('Post FX', 'Wheel Up/Down', 'Hue-shift frame (lasts 3 s idle)'),
    ('Post FX', 'Ctrl+Wheel Up/Down', 'Rotate scene frame (lasts 3 s idle)'),
    ('Post FX', 'Middle Click', 'Reset scroll FX (hue/rotation)'),
]


class PostFxController:
    """Runtime controller for global post-process effects."""

    SLOT_MAP: tuple[tuple[int, str, bool], ...] = (
        (1, 'Chromatic Aberration', True),
        (2, 'Film Grain + Dither', True),
        (3, 'Glitch Slices', True),
        (4, 'Heat Haze Refraction', True),
        (5, 'Lens Distortion + Vignette', True),
        (6, 'Multi-pass Bloom', True),
        (7, 'Radial Zoom Blur', True),
        (8, 'Temporal Feedback Trail', True),
        (9, 'Time Scramble Warp', True),
        (10, 'Smoke & Bubbles', True),
    )

    # Curated friend pairings for Post-FX ping-pong.
    # Keys are slot numbers; values are tuples of friendly partner slots.
    # Pairings are symmetric: if A lists B, B lists A.
    POSTFX_FRIENDS: dict[int, tuple[int, ...]] = {
        1: (3, 7),    # Chromatic Aberration ↔ Glitch Slices, Radial Zoom Blur
        3: (1, 9),    # Glitch Slices ↔ Chromatic Aberration, Time Scramble Warp
        4: (9, 8),    # Heat Haze ↔ Time Scramble Warp, Temporal Feedback Trail
        6: (7, 5),    # Bloom ↔ Radial Zoom Blur, Lens Distortion
        7: (6, 1),    # Radial Zoom Blur ↔ Bloom, Chromatic Aberration
        8: (4, 9),    # Temporal Feedback Trail ↔ Heat Haze, Time Scramble Warp
        9: (3, 4),    # Time Scramble Warp ↔ Glitch Slices, Heat Haze
    }

    @classmethod
    def friend_pairs(cls) -> list[tuple[int, int]]:
        """Return a deduplicated list of (a, b) slot pairs from POSTFX_FRIENDS.

        Each pair appears exactly once with a < b.
        """
        seen: set[tuple[int, int]] = set()
        result: list[tuple[int, int]] = []
        for slot, partners in cls.POSTFX_FRIENDS.items():
            for partner in partners:
                pair = (min(slot, partner), max(slot, partner))
                if pair not in seen:
                    seen.add(pair)
                    result.append(pair)
        return sorted(result)

    @classmethod
    def friend_groups(cls) -> list[tuple[int, ...]]:
        """Return all friend groups (pairs and trios) from POSTFX_FRIENDS.

        Includes every pair from ``friend_pairs()`` plus every distinct 3-way
        group implied by entries that have two partners.  Each group is
        deduplicated (same set of slots only appears once) and sorted
        internally by slot number.
        """
        seen: set[frozenset[int]] = set()
        result: list[tuple[int, ...]] = []
        for pair in cls.friend_pairs():
            key = frozenset(pair)
            if key not in seen:
                seen.add(key)
                result.append(pair)
        for slot, partners in cls.POSTFX_FRIENDS.items():
            if len(partners) >= 2:
                trio = tuple(sorted((slot,) + partners[:2]))
                key = frozenset(trio)
                if key not in seen:
                    seen.add(key)
                    result.append(trio)
        return result

    def __init__(self, ctx: moderngl.Context, width: int, height: int, cfg: dict | None = None) -> None:
        self._ctx = ctx
        self._width = width
        self._height = height
        self._cfg = cfg or {}
        self.enabled = bool(self._cfg.get('enabled', True))

        self._effects: dict[int, object] = {
            1: ChromaticAberration(ctx, width, height),
            2: FilmGrainDither(ctx, width, height),
            3: GlitchSlices(ctx, width, height),
            4: HeatHazeRefraction(ctx, width, height),
            5: LensDistortionVignette(ctx, width, height),
            6: MultiPassBloom(ctx, width, height),
            7: RadialZoomBlur(ctx, width, height),
            8: TemporalFeedbackTrail(ctx, width, height),
            9: TimeScrambleWarp(ctx, width, height),
            10: SmokeBubbles(ctx, width, height),
        }
        self._hit_duration = float(self._cfg.get('hit_duration', 0.9) or 0.9)
        self._slot_hit_duration: dict[int, float] = {
            1: float(self._cfg.get('slot1_duration', 1.15) or 1.15),
            2: float(self._cfg.get('slot2_duration', 0.95) or 0.95),
            3: float(self._cfg.get('slot3_duration', 0.90) or 0.90),
            4: float(self._cfg.get('slot4_duration', 1.30) or 1.30),
            5: float(self._cfg.get('slot5_duration', 1.05) or 1.05),
            6: float(self._cfg.get('slot6_duration', 1.20) or 1.20),
            7: float(self._cfg.get('slot7_duration', 0.95) or 0.95),
            8: float(self._cfg.get('slot8_duration', self._hit_duration) or self._hit_duration),
            9: float(self._cfg.get('slot9_duration', 0.85) or 0.85),
            10: float(self._cfg.get('slot10_duration', 2.40) or 2.40),
        }
        self._active_slot: int = 0
        self._active_effect = None
        self._active_t: float = 0.0
        self._debug_apply_signature: tuple[bool, bool, bool, int] | None = None

        # ── Hue-shift continuous pass (scroll-wheel driven) ──────────────
        self._hue_shift = HueShift(ctx, width, height)
        self._hue_offset: float = 0.0
        self._hue_active: bool = False
        self._hue_idle_t: float = 0.0
        self._hue_idle_timeout: float = float(self._cfg.get('hue_shift_timeout_s', 3.0) or 3.0)
        self._hue_step: float = float(self._cfg.get('hue_shift_step', 1.0 / 36.0) or 1.0 / 36.0)

        # ── Scene-rotation continuous pass (ctrl+scroll driven) ─────────
        self._scene_rotation = SceneRotation(ctx, width, height)
        self._rot_angle: float = 0.0
        self._rot_active: bool = False
        self._rot_idle_t: float = 0.0
        self._rot_idle_timeout: float = float(self._cfg.get('rotation_timeout_s', 3.0) or 3.0)
        self._rot_step_rad: float = float(self._cfg.get('rotation_step_rad', 0.07) or 0.07)

        # Internal FBO used when slot and hue passes both need to chain.
        self._hue_fbo: moderngl.Framebuffer = ctx.framebuffer(
            color_attachments=[ctx.texture((width, height), 4)]
        )

        default_slot = int(self._cfg.get('active_slot', 0) or 0)
        if default_slot > 0:
            self.trigger_slot(default_slot)

        log.debug(
            'PostFX init: enabled=%s size=%dx%d active_slot=%d durations=%s',
            self.enabled,
            self._width,
            self._height,
            default_slot,
            self._slot_hit_duration,
        )
        self._vj_api: Any = None

    def set_vj_api(self, api: Any) -> None:
        """Inject the VJApi instance after construction."""
        self._vj_api = api

    def handle_key(self, sym: int, mod: int) -> 'str | None | bool':
        """Handle Ctrl+Alt+1..9/0 — select post-FX slot.

        Shift is explicitly excluded so the ``Ctrl+Shift+Alt`` app leader (used by
        other drop-ins, e.g. the OSC bridge) does not collide with the digit slots.
        """
        import sdl2  # noqa: PLC0415
        if (
            (mod & sdl2.KMOD_CTRL)
            and (mod & sdl2.KMOD_ALT)
            and not (mod & sdl2.KMOD_SHIFT)
        ):
            if sdl2.SDLK_1 <= sym <= sdl2.SDLK_9:
                slot = sym - sdl2.SDLK_0
                if self._vj_api is not None:
                    return self._vj_api.select_postfx_slot(slot)
                self.trigger_slot(slot)
                return f'PostFX slot {slot}'
            if sym == sdl2.SDLK_0:
                if self._vj_api is not None:
                    return self._vj_api.select_postfx_slot(10)
                self.trigger_slot(10)
                return 'PostFX slot 10'
        return False

    def is_active(self) -> bool:
        return self.enabled and (
            (self._active_effect is not None and self._active_t > 0.0)
            or self._hue_active
            or self._rot_active
        )

    @property
    def is_hue_active(self) -> bool:
        """True while the scroll-wheel hue-shift pass is running."""
        return self._hue_active

    @property
    def is_rotation_active(self) -> bool:
        """True while the ctrl+scroll scene-rotation pass is running."""
        return self._rot_active

    @property
    def active_slot(self) -> int:
        """Return the currently active quick-hit slot, or 0 when inactive."""
        return self._active_slot

    @property
    def debug_summary(self) -> str:
        """Compact runtime state string for HUD/debug overlays."""
        slot = self._active_slot if self._active_slot > 0 else 0
        name = self.active_name
        return (
            f'en={int(self.enabled)} slot={slot}:{name} t={self._active_t:.2f} '
            f'hue={int(self._hue_active)}({self._hue_idle_t:.2f}) '
            f'rot={int(self._rot_active)}({self._rot_idle_t:.2f})'
        )

    def clear_active_slot(self) -> None:
        """Immediately clear the active quick-hit effect without touching hue shift."""
        self._active_slot = 0
        self._active_effect = None
        self._active_t = 0.0

    def on_scroll(self, dy: int) -> None:
        """Accumulate hue offset from a mouse-wheel event and (re)arm the idle timer.

        dy is positive for scroll-up and negative for scroll-down.
        """
        if not self.enabled:
            return
        self._hue_offset = (self._hue_offset + int(dy) * self._hue_step) % 1.0
        self._hue_idle_t = self._hue_idle_timeout
        self._hue_active = True
        log.debug('Hue shift: offset=%.3f dy=%d', self._hue_offset, dy)

    def on_ctrl_scroll(self, dy: int) -> None:
        """Accumulate scene rotation from a ctrl+mouse-wheel event."""
        if not self.enabled:
            return
        self._rot_angle += int(dy) * self._rot_step_rad
        self._rot_idle_t = self._rot_idle_timeout
        self._rot_active = True
        log.debug('Scene rotation: angle=%.3f dy=%d', self._rot_angle, dy)

    def on_ctrl_scroll_degrees(self, degrees: float) -> None:
        """Accumulate scene rotation by explicit degree amount."""
        if not self.enabled:
            return
        self._rot_angle += float(degrees) * 0.017453292519943295
        self._rot_idle_t = self._rot_idle_timeout
        self._rot_active = True
        log.debug('Scene rotation: angle=%.3f deg=%.2f', self._rot_angle, float(degrees))

    def clear_hue_shift(self) -> None:
        """Immediately deactivate the hue-shift pass and reset the offset."""
        self._hue_active = False
        self._hue_idle_t = 0.0
        self._hue_offset = 0.0
        log.debug('Hue shift cleared')

    def clear_rotation(self) -> None:
        """Immediately deactivate scene rotation and reset the angle."""
        self._rot_active = False
        self._rot_idle_t = 0.0
        self._rot_angle = 0.0
        log.debug('Scene rotation cleared')

    def clear_scroll_fx(self) -> None:
        """Clear both continuous scroll-driven post-fx states."""
        self.clear_hue_shift()
        self.clear_rotation()

    @property
    def active_name(self) -> str:
        if not self.is_active():
            return 'OFF'
        for slot_key, slot_name, _implemented in self.SLOT_MAP:
            if slot_key == self._active_slot:
                return slot_name
        return 'OFF'

    def trigger_slot(self, slot: int) -> str:
        """Trigger a one-shot post-process quick-hit by slot number."""
        max_slot = max((s[0] for s in self.SLOT_MAP), default=0)
        if slot <= 0:
            return f'Post FX: use Ctrl+Alt+1..{max_slot}'

        if slot < 0 or slot > max_slot:
            return f'Post FX: invalid slot {slot}'

        info = next((s for s in self.SLOT_MAP if s[0] == slot), None)
        if info is None:
            return f'Post FX: invalid slot {slot}'

        _slot_key, slot_name, implemented = info

        if not implemented or slot not in self._effects:
            return f'Post FX {slot}: {slot_name} (coming soon)'

        self._active_slot = slot
        self._active_effect = self._effects[slot]
        duration = self._slot_hit_duration.get(slot, self._hit_duration)
        self._active_t = max(0.05, duration)
        reset = getattr(self._active_effect, 'reset', None)
        if callable(reset):
            try:
                reset()
            except Exception as exc:
                log.warning('Post FX reset failed for %s: %s', slot_name, exc)
        log.debug('Post FX fired: slot=%d name=%s duration=%.2fs', slot, slot_name, self._active_t)
        return f'Post FX {slot}: {slot_name}'

    # Backward compatibility with earlier API name.
    def select_slot(self, slot: int) -> str:
        return self.trigger_slot(slot)

    def apply(
        self,
        src_tex: moderngl.Texture,
        dst_fbo: moderngl.Framebuffer,
        dt: float,
        bass: float,
        mid: float,
        treble: float,
        beat: float,
    ) -> bool:
        """Apply active post-fx passes into dst_fbo.

        Execution order when multiple passes are active:
          1. Slot one-shot → internal _hue_fbo
          2. Hue shift (if active)
          3. Scene rotation (if active)
        When only one pass is active it writes directly to dst_fbo.
        """
        if not self.is_active():
            return False

        slot_running = self._active_effect is not None and self._active_t > 0.0
        hue_running = self._hue_active
        rot_running = self._rot_active

        signature = (slot_running, hue_running, rot_running, self._active_slot)
        if signature != self._debug_apply_signature:
            log.debug(
                'PostFX apply state: slot=%s hue=%s rot=%s active_slot=%d t=%.3f',
                slot_running,
                hue_running,
                rot_running,
                self._active_slot,
                self._active_t,
            )
            self._debug_apply_signature = signature

        if slot_running:
            duration = self._slot_hit_duration.get(self._active_slot, self._hit_duration)
            strength = max(0.0, min(1.0, self._active_t / max(1e-6, duration)))
            slot_dst = self._hue_fbo if (hue_running or rot_running) else dst_fbo
            self._active_effect.apply(src_tex, slot_dst, dt, bass, mid, treble, beat, strength)
            self._active_t = max(0.0, self._active_t - dt)
            if self._active_t <= 0.0:
                log.debug('Post FX completed: slot=%d name=%s', self._active_slot, self.active_name)
                self.clear_active_slot()

        if hue_running:
            hue_src = self._hue_fbo.color_attachments[0] if slot_running else src_tex
            hue_dst = self._hue_fbo if rot_running else dst_fbo
            hue_strength = max(0.0, min(1.0, self._hue_idle_t / max(1e-6, self._hue_idle_timeout)))
            self._hue_shift.hue_offset = self._hue_offset
            self._hue_shift.apply(hue_src, hue_dst, dt, bass, mid, treble, beat, hue_strength)
            self._hue_idle_t = max(0.0, self._hue_idle_t - dt)
            if self._hue_idle_t <= 0.0:
                self._hue_active = False
                log.debug('Hue shift expired (idle timeout)')

        if rot_running:
            if slot_running or hue_running:
                rot_src = self._hue_fbo.color_attachments[0]
            else:
                rot_src = src_tex
            rot_strength = max(0.0, min(1.0, self._rot_idle_t / max(1e-6, self._rot_idle_timeout)))
            self._scene_rotation.angle = self._rot_angle
            self._scene_rotation.apply(rot_src, dst_fbo, dt, bass, mid, treble, beat, rot_strength)
            self._rot_idle_t = max(0.0, self._rot_idle_t - dt)
            if self._rot_idle_t <= 0.0:
                self._rot_active = False
                log.debug('Scene rotation expired (idle timeout)')

        return True

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        # Rebuild internal hue-chain FBO at new resolution.
        try:
            self._hue_fbo.color_attachments[0].release()
            self._hue_fbo.release()
            self._hue_fbo = self._ctx.framebuffer(
                color_attachments=[self._ctx.texture((width, height), 4)]
            )
        except Exception as exc:
            log.warning('Post FX hue FBO resize failed: %s', exc)
        self._hue_shift.resize(width, height)
        self._scene_rotation.resize(width, height)
        for effect in self._effects.values():
            try:
                effect.resize(width, height)
            except Exception as exc:
                log.warning('Post FX resize failed for %s: %s', getattr(effect, 'NAME', type(effect).__name__), exc)

    def destroy(self) -> None:
        try:
            self._hue_shift.destroy()
            self._scene_rotation.destroy()
            self._hue_fbo.color_attachments[0].release()
            self._hue_fbo.release()
        except Exception as exc:
            log.warning('Post FX hue resources destroy failed: %s', exc)
        for effect in self._effects.values():
            try:
                effect.destroy()
            except Exception as exc:
                log.warning('Post FX destroy failed for %s: %s', getattr(effect, 'NAME', type(effect).__name__), exc)
