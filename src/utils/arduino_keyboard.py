"""
Arduino Keyboard Wrapper - Monkey-patches the `keyboard` module to route
game input through Arduino HID while preserving local hotkey functionality.

Only keyboard.send(), keyboard.press(), keyboard.release() are intercepted.
keyboard.add_hotkey(), keyboard.wait(), keyboard.is_pressed() remain unchanged
since those are for local bot control, not game input.

Usage (in main.py, before any game logic):
    from utils.arduino_keyboard import install_arduino_keyboard
    install_arduino_keyboard(arduino_hid_instance)
"""

import keyboard
from utils.arduino_hid import ArduinoHID, SPECIAL_KEYS
from logger import Logger

# Keep references to originals
_original_send = keyboard.send
_original_press = keyboard.press
_original_release = keyboard.release

# Arduino HID instance (set by install)
_arduino: ArduinoHID = None


def _translate_key(key: str) -> str:
    """Normalize key names between keyboard lib and Arduino conventions.

    keyboard lib uses names like 'esc', 'enter', 'shift', 'alt', etc.
    Our Arduino HID expects these mapped through SPECIAL_KEYS.
    """
    # Map keyboard lib names to our SPECIAL_KEYS names
    key_map = {
        'shift': 'left_shift',
        'ctrl': 'left_ctrl',
        'alt': 'left_alt',
        'space': ' ',
        'spacebar': ' ',
    }
    key_lower = key.lower().strip()
    return key_map.get(key_lower, key_lower)


def _arduino_send(hotkey, do_press=True, do_release=True):
    """Replacement for keyboard.send() that routes through Arduino.

    Handles the do_press/do_release kwargs that botty uses for hold patterns like:
        keyboard.send("shift", do_release=False)  # hold shift
        ... do stuff ...
        keyboard.send("shift", do_press=False)    # release shift
    """
    if not _arduino or not _arduino.connected:
        _original_send(hotkey, do_press=do_press, do_release=do_release)
        return

    key = _translate_key(str(hotkey))

    if do_press and do_release:
        # Normal key press + release
        _arduino.key_press(key, hold_ms=50)
    elif do_press and not do_release:
        # Hold key down
        _arduino.key_down(key)
    elif not do_press and do_release:
        # Release held key
        _arduino.key_up(key)


def _arduino_press(hotkey):
    """Replacement for keyboard.press() — hold a key down."""
    if not _arduino or not _arduino.connected:
        _original_press(hotkey)
        return

    key = _translate_key(str(hotkey))
    _arduino.key_down(key)


def _arduino_release(hotkey):
    """Replacement for keyboard.release() — release a held key."""
    if not _arduino or not _arduino.connected:
        _original_release(hotkey)
        return

    key = _translate_key(str(hotkey))
    _arduino.key_up(key)


def install_arduino_keyboard(arduino_hid: ArduinoHID):
    """Monkey-patch keyboard module to route through Arduino HID.

    Only patches send/press/release. Leaves add_hotkey/wait/is_pressed alone
    since those are for local bot control hotkeys, not game input.
    """
    global _arduino
    _arduino = arduino_hid

    if _arduino and _arduino.connected:
        keyboard.send = _arduino_send
        keyboard.press = _arduino_press
        keyboard.release = _arduino_release
        Logger.info("Keyboard input routed through Arduino HID")
    else:
        Logger.info("Arduino not connected, keyboard using software fallback")


def uninstall_arduino_keyboard():
    """Restore original keyboard functions."""
    keyboard.send = _original_send
    keyboard.press = _original_press
    keyboard.release = _original_release
    Logger.info("Keyboard input restored to software")
