"""Smoke & bubbles post-process effect — Ibiza club fog with rising bubbles."""
from __future__ import annotations

import logging
import math

import moderngl

from base import FullscreenPass

log = logging.getLogger(__name__)


class SmokeBubbles:
    """Volumetric-feeling smoke overlay with audio-reactive rising bubbles.

    Visual recipe:
      * 3-octave FBM smoke is advected upward and modulated by bass so the
        whole frame breathes with the kick.
      * Three layers of cell-grid bubbles rise with size/density driven by
        bass, drift speed by mid, and rim shimmer by treble.
      * Beat impulses pulse a brief volumetric brightening for a "club hit".
    """

    NAME = 'Smoke & Bubbles'

    def __init__(self, ctx: moderngl.Context, width: int, height: int) -> None:
        self._ctx = ctx
        self._width = width
        self._height = height
        self._time = 0.0
        self._beat_pulse = 0.0
        self._pass = FullscreenPass.build(
            ctx,
            """
#version 330
// Smoke & Bubbles — Ibiza club post-fx pass.
// Inputs:
//   tex      : source frame
//   uTime    : seconds since start
//   uRes     : viewport size in pixels (for aspect correction)
//   uBass    : 0..1+, drives bubble density/size and smoke breathing
//   uMid     : 0..1+, drives drift speed
//   uTreble  : 0..1+, drives rim shimmer / spec highlights
//   uBeat    : 0..1, short-decay beat pulse for volumetric brightening
//   uStrength: 0..1 effect mix
uniform sampler2D tex;
uniform float uTime;
uniform vec2  uRes;
uniform float uBass;
uniform float uMid;
uniform float uTreble;
uniform float uBeat;
uniform float uStrength;

in vec2 v_uv;
out vec4 fragColor;

// ── Hash + value noise ────────────────────────────────────────────────
float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

vec2 hash22(vec2 p) {
    return vec2(
        hash21(p + 17.0),
        hash21(p - 31.0)
    );
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash21(i + vec2(0.0, 0.0));
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.55;
    for (int i = 0; i < 3; i++) {
        v += a * vnoise(p);
        p = p * 2.07 + vec2(13.1, 7.3);
        a *= 0.55;
    }
    return v;
}

// ── Bubble layer ──────────────────────────────────────────────────────
// Returns vec3(coverage, rim_highlight, spec_glint) summed over a layer.
vec3 bubble_layer(vec2 uv, float t, float cell, float speed,
                  float radius_scale, float density_gate) {
    // Cell grid in aspect-corrected space.
    vec2 gv = uv * cell;
    // Vertical drift upward over time.
    gv.y -= t * speed;
    vec2 id = floor(gv);
    vec2 fp = fract(gv) - 0.5;

    vec3 acc = vec3(0.0);

    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 off = vec2(float(i), float(j));
            vec2 nid = id + off;
            float h = hash21(nid + 19.7);
            if (h < density_gate) {
                continue;
            }

            // Per-cell wobble + jitter so bubbles don't sit on a grid.
            vec2 jitter = hash22(nid) - 0.5;
            float wobble_x = sin(t * (1.1 + h * 1.7) + h * 6.28) * 0.18;
            vec2 center = off + jitter * 0.55 + vec2(wobble_x, 0.0);

            float r = (0.18 + 0.30 * h) * radius_scale;
            vec2 dv = fp - center;
            float d = length(dv);

            float coverage = smoothstep(r, r * 0.88, d);
            float rim      = smoothstep(r * 1.02, r * 0.94, d)
                           - smoothstep(r * 0.94, r * 0.78, d);
            // Tiny offset specular dot — fake light from upper-left.
            vec2 spec_dv = dv - vec2(-r * 0.35, -r * 0.35);
            float spec = smoothstep(r * 0.22, 0.0, length(spec_dv));

            acc.x += coverage;
            acc.y += rim;
            acc.z += spec * coverage;
        }
    }
    return acc;
}

void main() {
    vec2 uv  = v_uv;
    vec3 src = texture(tex, uv).rgb;

    float s  = clamp(uStrength, 0.0, 1.0);
    float t  = uTime;
    float aspect = max(uRes.x, 1.0) / max(uRes.y, 1.0);
    vec2  uva = vec2(uv.x * aspect, uv.y);

    // ── Smoke fog ─────────────────────────────────────────────────────
    float drift = 0.06 + 0.22 * clamp(uMid, 0.0, 2.0);
    vec2  sp = uva * 2.6 + vec2(t * 0.08, -t * drift);
    float smoke = fbm(sp);
    smoke += 0.35 * fbm(sp * 2.2 - vec2(t * 0.13, t * 0.05));
    smoke = smoothstep(0.35, 1.05, smoke);
    // Heavier near the floor (Ibiza low-fog feel).
    smoke *= mix(0.55, 1.10, 1.0 - uv.y);
    // Bass breathing.
    float bass = clamp(uBass, 0.0, 2.0);
    smoke *= 0.85 + 0.35 * bass;

    vec3 smoke_color = mix(
        vec3(0.06, 0.08, 0.12),
        vec3(0.55, 0.62, 0.78),
        smoke
    );

    // ── Bubbles: 3 stacked layers for depth ──────────────────────────
    float bub_speed   = 0.18 + 0.42 * clamp(uMid, 0.0, 2.0);
    float bub_scale   = 1.0 + 0.45 * bass;
    float bub_density = mix(0.78, 0.55, clamp(bass * 0.6, 0.0, 1.0));

    vec3 b0 = bubble_layer(uva, t, 7.0,  bub_speed * 0.45, 1.20 * bub_scale, bub_density);
    vec3 b1 = bubble_layer(uva, t + 13.7, 11.0, bub_speed * 0.75, 0.90 * bub_scale, bub_density + 0.02);
    vec3 b2 = bubble_layer(uva, t + 27.3, 17.0, bub_speed * 1.10, 0.65 * bub_scale, bub_density + 0.04);

    float coverage = clamp(b0.x * 0.55 + b1.x * 0.35 + b2.x * 0.25, 0.0, 1.0);
    float rim      = clamp(b0.y + b1.y * 0.85 + b2.y * 0.7,         0.0, 1.0);
    float spec     = clamp(b0.z + b1.z * 0.9  + b2.z * 0.85,        0.0, 1.0);

    // Bubble body color — slight chromatic refraction sampled from source.
    vec2 chro = vec2(0.004, 0.0);
    float r = texture(tex, uv + chro).r;
    float g = texture(tex, uv).g;
    float bC = texture(tex, uv - chro).b;
    vec3 refr = vec3(r, g, bC);
    vec3 bubble_body = mix(refr * 1.05, vec3(0.85, 0.93, 1.0), 0.18);

    // Treble shimmer pumps rim brightness.
    float shimmer = 0.55 + 0.75 * clamp(uTreble, 0.0, 2.0);

    // Beat brightening — volumetric flash.
    float beat = clamp(uBeat, 0.0, 1.0);
    float flash = beat * 0.35;

    // ── Composite ─────────────────────────────────────────────────────
    // 1) Darken source with smoke.
    vec3 col = mix(src, src * 0.55 + smoke_color * 0.75, smoke * 0.85);
    // 2) Add club flash through the smoke.
    col += smoke_color * flash;
    // 3) Bubble body over smoke.
    col = mix(col, bubble_body, coverage * 0.75);
    // 4) Rim highlight (treble shimmer).
    col += vec3(0.85, 0.92, 1.0) * rim * 0.55 * shimmer;
    // 5) Spec glint dot.
    col += vec3(1.0) * spec * 0.85;

    // Final wet/dry blend by strength.
    vec3 outc = mix(src, col, s);
    fragColor = vec4(clamp(outc, 0.0, 1.0), 1.0);
}
""",
        )

    def apply(
        self,
        src_tex: moderngl.Texture,
        dst_fbo: moderngl.Framebuffer,
        dt: float,
        bass: float,
        mid: float,
        treble: float,
        beat: float,
        strength: float,
    ) -> None:
        self._time += dt
        # Exponential decay on a separate beat pulse so we get a brief flash
        # even when the host beat signal is only an instantaneous spike.
        self._beat_pulse = max(0.0, self._beat_pulse - dt * 3.5)
        if beat > self._beat_pulse:
            self._beat_pulse = min(1.0, float(beat))

        dst_fbo.use()
        self._ctx.viewport = (0, 0, dst_fbo.size[0], dst_fbo.size[1])
        self._ctx.clear(0.0, 0.0, 0.0, 1.0)
        src_tex.use(location=0)

        prog = self._pass.prog
        prog['tex'].value = 0
        prog['uTime'].value = float(self._time)
        prog['uRes'].value = (float(dst_fbo.size[0]), float(dst_fbo.size[1]))
        prog['uBass'].value = float(bass)
        prog['uMid'].value = float(mid)
        prog['uTreble'].value = float(treble)
        prog['uBeat'].value = float(self._beat_pulse)
        prog['uStrength'].value = max(0.0, min(1.0, float(strength)))
        self._pass.vao.render(moderngl.TRIANGLE_STRIP)

    def reset(self) -> None:
        """Randomize phase so each trigger looks slightly different."""
        self._time += 7.31 + math.fmod(self._time * 0.137, 5.0)
        self._beat_pulse = 0.0

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def destroy(self) -> None:
        self._pass.release()
