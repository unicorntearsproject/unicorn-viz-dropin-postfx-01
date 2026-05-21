"""Time-scramble warp post-process effect.

Intentional recreation of the old speed-slew scramble vibe as an on-demand
post-fx hit, rather than an accidental side-effect of parameter slewing.
"""
from __future__ import annotations

import logging

import moderngl

from base import FullscreenPass

log = logging.getLogger(__name__)


class TimeScrambleWarp:
    """Quick-hit phase-surge warp matching the old speed-slew bug signature."""

    NAME = 'Time Scramble Warp'

    def __init__(self, ctx: moderngl.Context, width: int, height: int) -> None:
        self._ctx = ctx
        self._width = width
        self._height = height
        self._time = 0.0
        self._pass = FullscreenPass.build(
            ctx,
            """
#version 330
uniform sampler2D tex;
uniform float uTime;
uniform float uAmount;
in vec2 v_uv;
out vec4 fragColor;

float sat(float x) {
    return clamp(x, 0.0, 1.0);
}

void main() {
    // This intentionally emulates the old speed-slew discontinuity:
    // whole-frame apparent "time jumps" (not line-slice glitches).
    vec2 uv = v_uv;
    vec2 p = uv - 0.5;

    float amount = sat(uAmount);
    float t = uTime;

    // Phase surge: mixes smooth and quantized clocks to feel like
    // tiny slew steps repeatedly punching giant phase jumps.
    float smoothClock = t * (2.2 + amount * 3.2);
    float steppedClock = floor(t * (12.0 + amount * 22.0)) * (0.06 + amount * 0.05);
    float surge = smoothClock + steppedClock;

    // Global rotational/zoom fold (the old bug looked like everything sped up,
    // warped, and twisted globally during the slew window).
    float r = length(p);
    float ang = atan(p.y, p.x);
    float rot = sin(surge * 1.8) * (0.05 + amount * 0.16);
    float zoom = 1.0 + sin(surge * 2.1 + r * 13.0) * (0.02 + amount * 0.09);
    float c = cos(rot);
    float s = sin(rot);
    vec2 pr = mat2(c, -s, s, c) * p;
    vec2 uvFold = 0.5 + pr / zoom;

    // Multi-tap temporal fold from one source texture: mimics the "over-speed"
    // smearing/ghosting without requiring frame history buffers.
    float jitter = (0.004 + amount * 0.03);
    vec2 jx = vec2(jitter * sin(surge * 4.1 + r * 21.0), 0.0);
    vec2 jy = vec2(0.0, jitter * cos(surge * 3.6 + r * 17.0));

    vec3 c0 = texture(tex, clamp(uvFold, 0.0, 1.0)).rgb;
    vec3 c1 = texture(tex, clamp(uvFold + jx, 0.0, 1.0)).rgb;
    vec3 c2 = texture(tex, clamp(uvFold - jy, 0.0, 1.0)).rgb;
    vec3 c3 = texture(tex, clamp(uvFold + jx - jy, 0.0, 1.0)).rgb;
    vec3 fold = (c0 * 0.46 + c1 * 0.22 + c2 * 0.20 + c3 * 0.12);

    // Chroma drift pulse (the old artifact also had weird color shifts).
    float split = 0.002 + amount * 0.02;
    vec2 dx = vec2(split * sin(surge * 3.2), 0.0);
    vec2 dy = vec2(0.0, split * cos(surge * 2.8));
    float rr = texture(tex, clamp(uvFold + dx, 0.0, 1.0)).r;
    float gg = texture(tex, clamp(uvFold,      0.0, 1.0)).g;
    float bb = texture(tex, clamp(uvFold - dy, 0.0, 1.0)).b;
    vec3 chroma = vec3(rr, gg, bb);

    float mixAmt = 0.24 + amount * 0.62;
    vec3 col = mix(fold, chroma, mixAmt);

    // Energy pulse/contrast squeeze to finish the "flip-out" feel.
    float pulse = 1.0 + sin(surge * 6.0 + r * 20.0) * (0.05 + amount * 0.16);
    col *= pulse;
    col = pow(max(col, 0.0), vec3(0.92 - amount * 0.18));
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
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
        dst_fbo.use()
        self._ctx.viewport = (0, 0, dst_fbo.size[0], dst_fbo.size[1])
        self._ctx.clear(0.0, 0.0, 0.0, 1.0)
        src_tex.use(location=0)
        self._pass.prog['tex'].value = 0
        self._pass.prog['uTime'].value = self._time
        s = max(0.0, min(1.0, float(strength)))
        amt = 0.28 + 0.62 * s + min(0.28, beat * 0.20 + treble * 0.10 + mid * 0.08 + bass * 0.06)
        self._pass.prog['uAmount'].value = amt
        self._pass.vao.render(moderngl.TRIANGLE_STRIP)
        log.debug('TimeScrambleWarp firing: strength=%.2f amount=%.3f', s, amt)

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def reset(self) -> None:
        """Reset effect timeline on trigger."""
        self._time = 0.0

    def destroy(self) -> None:
        self._pass.release()
