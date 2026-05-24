"""Scene rotation post-process effect.

Full-frame UV rotation driven by cumulative Ctrl+scroll input.
Controlled by PostFxController.on_ctrl_scroll() / clear_rotation().
Not a numbered slot effect; applied as a persistent overlay pass
independently of the one-shot slot pipeline.
"""
from __future__ import annotations

import moderngl

from postfx_effects_base import FullscreenPass

_FRAG = """
#version 330

uniform sampler2D tex;
uniform float uAngle;
uniform float uMix;

in vec2 v_uv;
out vec4 fragColor;

void main() {
    vec2 p = v_uv - 0.5;
    float c = cos(uAngle);
    float s = sin(uAngle);
    vec2 pr = mat2(c, -s, s, c) * p;
    vec2 uv = clamp(pr + 0.5, 0.0, 1.0);
    vec3 src = texture(tex, v_uv).rgb;
    vec3 rot = texture(tex, uv).rgb;
    float m = clamp(uMix, 0.0, 1.0);
    fragColor = vec4(mix(src, rot, m), 1.0);
}
"""


class SceneRotation:
    """Full-frame scene rotation pass."""

    NAME = 'Scene Rotation'

    def __init__(self, ctx: moderngl.Context, width: int, height: int) -> None:
        self._ctx = ctx
        self._width = width
        self._height = height
        self._pass = FullscreenPass.build(ctx, _FRAG)
        self.angle: float = 0.0
        self.blend: float = 1.0

    def apply(
        self,
        src_tex: moderngl.Texture,
        dst_fbo: moderngl.Framebuffer,
        dt: float,          # noqa: ARG002
        bass: float,        # noqa: ARG002
        mid: float,         # noqa: ARG002
        treble: float,      # noqa: ARG002
        beat: float,        # noqa: ARG002
        strength: float,
    ) -> None:
        """Render rotated frame from src_tex into dst_fbo."""
        dst_fbo.use()
        self._ctx.viewport = (0, 0, dst_fbo.size[0], dst_fbo.size[1])
        self._ctx.clear(0.0, 0.0, 0.0, 1.0)
        src_tex.use(location=0)
        self._pass.prog['tex'].value = 0
        self._pass.prog['uAngle'].value = float(self.angle)
        self._pass.prog['uMix'].value = max(0.0, min(1.0, float(strength) * self.blend))
        self._pass.vao.render(moderngl.TRIANGLE_STRIP)

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def destroy(self) -> None:
        self._pass.release()
