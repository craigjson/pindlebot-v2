"""
Arduino HID Interface - Serial communication with Arduino Leonardo/Pro Micro.
Sends commands that the Arduino converts to real USB HID keyboard/mouse events.
"""

import time
import serial
import serial.tools.list_ports
from logger import Logger

# Special key codes matching Arduino Keyboard.h
SPECIAL_KEYS = {
    'esc': 177,
    'escape': 177,
    'enter': 176,
    'return': 176,
    'tab': 179,
    'backspace': 178,
    'insert': 209,
    'delete': 212,
    'home': 210,
    'end': 213,
    'pageup': 211,
    'pagedown': 214,
    'up': 218,
    'down': 217,
    'left': 216,
    'right': 215,
    'left_ctrl': 128,
    'left_shift': 129,
    'left_alt': 130,
    'right_ctrl': 132,
    'right_shift': 133,
    'right_alt': 134,
    'f1': 194,
    'f2': 195,
    'f3': 196,
    'f4': 197,
    'f5': 198,
    'f6': 199,
    'f7': 200,
    'f8': 201,
    'f9': 202,
    'f10': 203,
    'f11': 204,
    'f12': 205,
}


class ArduinoHID:
    def __init__(self, port='COM3', baud=115200, timeout=1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.serial = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to the Arduino. Returns True on success."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=self.timeout
            )
            # Wait for Arduino to reset after serial connection
            time.sleep(2.0)
            # Flush any startup messages
            self.serial.reset_input_buffer()
            self.connected = True
            Logger.info(f"Connected to Arduino on {self.port}")
            return True
        except serial.SerialException as e:
            Logger.error(f"Failed to connect to Arduino on {self.port}: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the Arduino."""
        if self.serial and self.serial.is_open:
            try:
                self._send("PING")
                self.serial.close()
            except Exception:
                pass
        self.connected = False
        Logger.info("Disconnected from Arduino")

    def _send(self, command: str, wait_ack=True) -> bool:
        """Send a command to the Arduino. Returns True if acknowledged."""
        if not self.connected or not self.serial or not self.serial.is_open:
            Logger.warning(f"Cannot send command, not connected: {command}")
            return False

        try:
            self.serial.write(f"{command}\n".encode('ascii'))
            self.serial.flush()

            if wait_ack:
                response = self.serial.readline().decode('ascii').strip()
                if response == 'OK':
                    return True
                elif response == 'SAFETY':
                    Logger.warning("Arduino safety timeout triggered")
                    return False
                elif response.startswith('ERR'):
                    Logger.error(f"Arduino error: {response}")
                    return False
                else:
                    Logger.debug(f"Unexpected response: {response}")
                    return True  # Don't fail on unexpected responses
            return True
        except serial.SerialException as e:
            Logger.error(f"Serial error sending command: {e}")
            self.connected = False
            return False

    def key_press(self, key: str, hold_ms: int = 50):
        """Press and release a key. Handles both regular and special keys."""
        key_lower = key.lower()
        if key_lower in SPECIAL_KEYS:
            self.special_key(SPECIAL_KEYS[key_lower], hold_ms)
        elif len(key) == 1:
            self._send(f"KEY:{key}:{hold_ms}")
        else:
            Logger.warning(f"Unknown key: {key}")

    def key_down(self, key: str):
        """Press and hold a key."""
        key_lower = key.lower()
        if len(key) == 1:
            self._send(f"KEY_DOWN:{key}")
        elif key_lower in SPECIAL_KEYS:
            self._send(f"KEY_DOWN:{chr(SPECIAL_KEYS[key_lower])}")

    def key_up(self, key: str):
        """Release a held key."""
        key_lower = key.lower()
        if len(key) == 1:
            self._send(f"KEY_UP:{key}")
        elif key_lower in SPECIAL_KEYS:
            self._send(f"KEY_UP:{chr(SPECIAL_KEYS[key_lower])}")

    def special_key(self, keycode: int, hold_ms: int = 50):
        """Press a special key by Arduino keycode."""
        self._send(f"SPECIAL:{keycode}:{hold_ms}")

    def mouse_move_relative(self, dx: int, dy: int, wait_ack=False):
        """Send a single relative mouse movement step. Clamped to [-127, 127]."""
        dx = max(-127, min(127, dx))
        dy = max(-127, min(127, dy))
        self._send(f"MOUSE_MOVE:{dx}:{dy}", wait_ack=wait_ack)

    def mouse_click(self, button: str = 'left', hold_ms: int = 50):
        """Click a mouse button."""
        btn_code = 2 if button == 'right' else (3 if button == 'middle' else 1)
        self._send(f"MOUSE_CLICK:{btn_code}:{hold_ms}")

    def mouse_down(self, button: str = 'left'):
        """Press and hold a mouse button."""
        btn_code = 2 if button == 'right' else (3 if button == 'middle' else 1)
        self._send(f"MOUSE_DOWN:{btn_code}")

    def mouse_up(self, button: str = 'left'):
        """Release a mouse button."""
        btn_code = 2 if button == 'right' else (3 if button == 'middle' else 1)
        self._send(f"MOUSE_UP:{btn_code}")

    def type_string(self, text: str, hold_ms: int = 30):
        """Type a string character by character."""
        self._send(f"KEYS:{text}:{hold_ms}")

    @staticmethod
    def find_arduino_port() -> str | None:
        """Auto-detect Arduino Leonardo/Pro Micro by USB VID:PID."""
        arduino_ids = [
            (0x2341, 0x8036),  # Arduino Leonardo
            (0x2341, 0x8037),  # Arduino Micro
            (0x1B4F, 0x9205),  # SparkFun Pro Micro 5V
            (0x1B4F, 0x9206),  # SparkFun Pro Micro 3.3V
        ]

        for port_info in serial.tools.list_ports.comports():
            for vid, pid in arduino_ids:
                if port_info.vid == vid and port_info.pid == pid:
                    Logger.info(f"Found Arduino on {port_info.device} ({port_info.description})")
                    return port_info.device

        Logger.warning("No Arduino found via auto-detection")
        return None
