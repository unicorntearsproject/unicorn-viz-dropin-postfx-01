"""postfx-01's Control Room operator panel (P2 of
docs/planning/control-room-drop-in-integration-plan-2026-09-05.md).
Retires control-room-01's hardcoded POST FX panel, which read
vj_api.postfx_slots()/set_postfx_slot() -- a duck-typed reach into this
controller's own SLOT_MAP via app internals. Headless GL context, same
pattern as beat-flash-01/color-grade-01's controller tests.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parents[1] / 'postfx_controller.py'
_spec = importlib.util.spec_from_file_location('postfx_controller_test', _MOD)
ctrl_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ctrl_mod
_spec.loader.exec_module(ctrl_mod)
PostFxController = ctrl_mod.PostFxController


@pytest.fixture
def ctx():
    moderngl = pytest.importorskip('moderngl')
    try:
        c = moderngl.create_standalone_context()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f'no headless GL context: {exc}')
    yield c
    c.release()


class _FakeVJApi:
    def __init__(self) -> None:
        self.panels: dict[str, object] = {}

    def register_operator_panel(self, panel) -> None:
        self.panels[panel.name] = panel

    def unregister_operator_panel(self, name: str) -> bool:
        return self.panels.pop(name, None) is not None


def test_set_vj_api_registers_a_full_width_panel_on_the_fx_page(ctx) -> None:
    c = PostFxController(ctx, 64, 64, {})
    api = _FakeVJApi()
    c.set_vj_api(api)
    panel = api.panels['postfx']
    assert panel.title == 'Post FX' and panel.page == 'fx' and panel.size == 'full'
    assert panel.content == c._operator_panel_content
    assert panel.on_action == c._operator_panel_action
    assert 'clear' in panel.tooltips
    assert all(f'slot_{slot}' in panel.tooltips for slot, _n, _i in c.SLOT_MAP)
    c.destroy()


def test_panel_has_one_button_per_implemented_slot_plus_clear(ctx) -> None:
    c = PostFxController(ctx, 64, 64, {})
    content = c._operator_panel_content()
    labels = [b.label for b in content.buttons]
    assert labels == [str(slot) for slot, _n, impl in c.SLOT_MAP if impl] + ['CLR']
    assert content.status == 'ON'  # enabled defaults True, no slot active yet
    c.destroy()


def test_panel_status_is_off_when_disabled_and_no_slot_active(ctx) -> None:
    c = PostFxController(ctx, 64, 64, {'enabled': False})
    assert c._operator_panel_content().status == 'OFF'
    c.destroy()


def test_active_slot_marks_its_button_active_and_sets_status(ctx) -> None:
    c = PostFxController(ctx, 64, 64, {})
    c.trigger_slot(3)
    content = c._operator_panel_content()
    assert content.status == c.active_name
    active_buttons = {b.label for b in content.buttons if b.active}
    assert active_buttons == {'3'}
    c.destroy()


def test_slot_action_routes_to_trigger_slot_and_flashes_the_same_text(ctx) -> None:
    c = PostFxController(ctx, 64, 64, {})
    direct = c.trigger_slot(5)
    c.clear_active_slot()
    via_panel = c._operator_panel_action('slot_5', None)
    assert via_panel == direct
    c.destroy()


def test_clear_action_routes_to_clear_active_slot(ctx) -> None:
    c = PostFxController(ctx, 64, 64, {})
    c.trigger_slot(2)
    assert c.active_slot == 2
    msg = c._operator_panel_action('clear', None)
    assert c.active_slot == 0
    assert msg == 'Post FX cleared'
    assert c._operator_panel_action('nope', None) is None
    c.destroy()


def test_destroy_unregisters_the_panel(ctx) -> None:
    c = PostFxController(ctx, 64, 64, {})
    api = _FakeVJApi()
    c.set_vj_api(api)
    c.destroy()
    assert 'postfx' not in api.panels
