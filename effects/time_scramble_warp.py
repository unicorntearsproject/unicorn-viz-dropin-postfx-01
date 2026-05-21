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
    """Quick-hit temporal warp + chroma split glitch."""

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

float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

void main() {
    vec2 uv = v_uv;

    // Horizontal time-scramble bands.
    float bands = 56.0;
    float band = floor(uv.y * bands);
    float seed = band * 23.0 + floor(uTime * 48.0);
    float rnd = hash11(seed);
    float trigger = step(0.45, rnd);
    float bandShift = (rnd - 0.5) * (0.22 + uAmount * 0.42) * trigger;
    uv.x = clamp(uv.x + bandShift, 0.0, 1.0);

    // Radial wobble to emulate the "everything goes hyper" feel.
    vec2 p = uv - 0.5;
    float r = length(p);
    float a = atan(p.y, p.x);
    float wobble = sin(a * 8.0 + uTime * (10.0 + uAmount * 14.0)) * (0.012 + uAmount * 0.03);
    uv += normalize(p + 1e-6) * wobble * smoothstep(0.1, 0.9, r);
    uv = clamp(uv, 0.0, 1.0);

    // Chroma split accent.
    float split = 0.006 + uAmount * 0.028;
    vec2 dx = vec2(split, 0.0);
    float rch = texture(tex, clamp(uv + dx, 0.0, 1.0)).r;
    float gch = texture(tex, uv).g;
    float bch = texture(tex, clamp(uv - dx, 0.0, 1.0)).b;
    vec3 col = vec3(rch, gch, bch);

    // Light luma crush/push pulses for extra impact.
    float pulse = 1.0 + sin(uTime * 22.0) * (0.06 + uAmount * 0.10);
    col *= pulse;
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
        log.info('TimeScrambleWarp firing: strength=%.2f amount=%.3f', s, amt)

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def reset(self) -> None:
        """Reset effect timeline on trigger."""
        self._time = 0.0

    def destroy(self) -> None:
        self._pass.release()
