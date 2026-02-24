"""
Mouse abstraction layer - Routes through Arduino HID when available,
falls back to software mouse library otherwise.

All 37+ files in botty import `mouse` from this module.
The public API (mouse.move, mouse.click, mouse.press, mouse.release,
mouse.get_position, mouse.wheel) is unchanged.
"""

import random
import math
import time
import ctypes
from ctypes import wintypes

import screen
from config import Config
from utils.misc import is_in_roi
from logger import Logger
import template_finder

# Arduino HID backend (set by initialize_arduino())
_arduino = None
# Humanizer for Bezier curves and timing (set by initialize_arduino())
_humanizer = None
# Software fallback
_software_mouse = None

def _init_software_fallback():
    """Lazy-load the software mouse library as fallback."""
    global _software_mouse
    if _software_mouse is None:
        try:
            import mouse as _mouse_lib
            _software_mouse = _mouse_lib
        except ImportError:
            Logger.warning("mouse library not available for fallback")

def initialize_arduino(arduino_hid=None, humanizer=None):
    """Called once from main.py to set up Arduino HID backend.

    Args:
        arduino_hid: Connected ArduinoHID instance (or None to use software fallback)
        humanizer: Humanizer instance for Bezier curves and timing
    """
    global _arduino, _humanizer
    _arduino = arduino_hid
    _humanizer = humanizer
    if _arduino and _arduino.connected:
        Logger.info("Mouse routing through Arduino HID")
    else:
        Logger.info("Mouse routing through software fallback")
        _init_software_fallback()

def _use_arduino() -> bool:
    """Check if Arduino is connected and should be used."""
    return _arduino is not None and _arduino.connected

def _get_cursor_pos() -> tuple[int, int]:
    """Get current cursor position via Windows API (works regardless of input method)."""
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y)

def _move_arduino(from_x, from_y, to_x, to_y, delay_factor):
    """Move mouse from (from_x, from_y) to (to_x, to_y) via Arduino relative steps."""
    dist = math.sqrt((to_x - from_x) ** 2 + (to_y - from_y) ** 2)

    # Generate Bezier curve path
    points = _humanizer.bezier_points((from_x, from_y), (to_x, to_y))

    # Total movement duration (matches botty's original timing)
    duration = min(0.5, max(0.05, dist * 0.0004) * random.uniform(delay_factor[0], delay_factor[1]))
    step_delay = duration / max(len(points), 1)

    # Walk the Bezier path, sending relative deltas to Arduino
    prev_x, prev_y = from_x, from_y
    for px, py in points:
        dx = int(px - prev_x)
        dy = int(py - prev_y)

        # Break large deltas into Arduino's +-127 range
        while abs(dx) > 0 or abs(dy) > 0:
            step_dx = max(-127, min(127, dx))
            step_dy = max(-127, min(127, dy))
            _arduino.mouse_move_relative(step_dx, step_dy)
            dx -= step_dx
            dy -= step_dy

        prev_x, prev_y = px, py
        time.sleep(step_delay)


class mouse:
    @staticmethod
    def move(x, y, absolute: bool = True, randomize: int | tuple[int, int] = 5, delay_factor: tuple[float, float] = [0.4, 0.6]):
        """Move mouse to target position with humanized Bezier curve.

        Args:
            x, y: Target position in monitor (absolute screen) coordinates
            absolute: If True, x/y are absolute; if False, relative to current
            randomize: Pixel jitter to add to target. Int for uniform, tuple for (x, y) range.
            delay_factor: Speed multiplier range [min, max]
        """
        from_point = mouse.get_position()

        if not absolute:
            x = from_point[0] + x
            y = from_point[1] + y

        # Apply randomization jitter to target
        if type(randomize) is int:
            randomize = int(randomize)
            if randomize > 0:
                x = int(x) + random.randrange(-randomize, +randomize)
                y = int(y) + random.randrange(-randomize, +randomize)
        else:
            randomize = (int(randomize[0]), int(randomize[1]))
            if randomize[1] > 0 and randomize[0] > 0:
                x = int(x) + random.randrange(-randomize[0], +randomize[0])
                y = int(y) + random.randrange(-randomize[1], +randomize[1])

        if _use_arduino():
            _move_arduino(from_point[0], from_point[1], int(x), int(y), delay_factor)
        else:
            _init_software_fallback()
            if _software_mouse:
                # Use original botty movement via software mouse
                _software_mouse.move(int(x), int(y))

    @staticmethod
    def _is_clicking_safe():
        """Check if inventory is open and prevent clicks in equipped area."""
        mouse_pos = screen.convert_monitor_to_screen(mouse.get_position())
        is_inventory_open = template_finder.search(
            "INVENTORY_GOLD_BTN",
            screen.grab(),
            threshold=0.8,
            roi=Config().ui_roi["gold_btn"],
            use_grayscale=True
        ).valid
        if is_inventory_open:
            is_in_equipped_area = is_in_roi(Config().ui_roi["equipped_inventory_area"], mouse_pos)
            is_in_restricted_inventory_area = is_in_roi(Config().ui_roi["restricted_inventory_area"], mouse_pos)
            if is_in_restricted_inventory_area or is_in_equipped_area:
                Logger.error("Mouse wants to click in equipped area. Cancel action.")
                return False
        return True

    @staticmethod
    def click(button):
        """Click a mouse button."""
        if button != "left" or mouse._is_clicking_safe():
            if _use_arduino():
                hold_ms = max(30, int(random.gauss(60, 15)))
                _arduino.mouse_click(button, hold_ms)
            else:
                _init_software_fallback()
                if _software_mouse:
                    _software_mouse.click(button)

    @staticmethod
    def press(button):
        """Press and hold a mouse button."""
        if button != "left" or mouse._is_clicking_safe():
            if _use_arduino():
                _arduino.mouse_down(button)
            else:
                _init_software_fallback()
                if _software_mouse:
                    _software_mouse.press(button)

    @staticmethod
    def release(button):
        """Release a mouse button."""
        if _use_arduino():
            _arduino.mouse_up(button)
        else:
            _init_software_fallback()
            if _software_mouse:
                _software_mouse.release(button)

    @staticmethod
    def get_position():
        """Get current mouse position in monitor coordinates."""
        if _use_arduino():
            # Use Windows API directly — works regardless of how mouse was moved
            return _get_cursor_pos()
        else:
            _init_software_fallback()
            if _software_mouse:
                return _software_mouse.get_position()
            return _get_cursor_pos()

    @staticmethod
    def wheel(delta):
        """Scroll mouse wheel. Not supported via Arduino, uses software fallback."""
        _init_software_fallback()
        if _software_mouse:
            _software_mouse.wheel(delta)
        else:
            Logger.warning("Mouse wheel not available (no Arduino support, no software fallback)")


if __name__ == "__main__":
    import os
    import keyboard
    keyboard.add_hotkey('f12', lambda: os._exit(1))
    keyboard.wait("f11")
    screen.find_and_set_window_position()
    move_to_ok = screen.convert_screen_to_monitor((400, 420))
    move_to_bad_equiped = screen.convert_screen_to_monitor((900, 170))
    move_to_bad_inventory = screen.convert_screen_to_monitor((1200, 400))
    mouse.move(*move_to_ok)
    mouse.click("left")
    time.sleep(1)
    mouse.move(*move_to_bad_equiped)
    mouse.click("left")
    time.sleep(1)
    mouse.move(*move_to_bad_inventory)
    mouse.click("left")
