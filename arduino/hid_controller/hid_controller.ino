/*
 * D2R Pindle Bot - Arduino HID Controller
 * For Arduino Leonardo / Pro Micro (ATmega32U4)
 *
 * Receives serial commands at 115200 baud and outputs
 * real USB HID keyboard/mouse events.
 *
 * Commands (newline-terminated):
 *   KEY:<char>:<hold_ms>
 *   KEYS:<string>:<hold_ms>
 *   SPECIAL:<keycode>:<hold_ms>
 *   MOUSE_MOVE:<dx>:<dy>
 *   MOUSE_CLICK:<button>:<hold_ms>
 *   MOUSE_DOWN:<button>
 *   MOUSE_UP:<button>
 *   KEY_DOWN:<char>
 *   KEY_UP:<char>
 *
 * Safety: releases all keys/buttons if no data for 30 seconds.
 */

#include <Keyboard.h>
#include <Mouse.h>

#define SERIAL_BAUD 115200
#define BUFFER_SIZE 128
#define SAFETY_TIMEOUT_MS 30000

char buffer[BUFFER_SIZE];
int bufferIndex = 0;
unsigned long lastCommandTime = 0;
bool safetyTriggered = false;

void setup() {
    Serial.begin(SERIAL_BAUD);
    Keyboard.begin();
    Mouse.begin();
    lastCommandTime = millis();
}

void loop() {
    // Read serial data
    while (Serial.available() > 0) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (bufferIndex > 0) {
                buffer[bufferIndex] = '\0';
                processCommand(buffer);
                bufferIndex = 0;
                lastCommandTime = millis();
                safetyTriggered = false;
            }
        } else if (bufferIndex < BUFFER_SIZE - 1) {
            buffer[bufferIndex++] = c;
        }
    }

    // Safety watchdog: release everything if no commands for 30s
    if (!safetyTriggered && (millis() - lastCommandTime > SAFETY_TIMEOUT_MS)) {
        releaseAll();
        safetyTriggered = true;
        Serial.println("SAFETY");
    }
}

void releaseAll() {
    Keyboard.releaseAll();
    Mouse.release(MOUSE_LEFT);
    Mouse.release(MOUSE_RIGHT);
    Mouse.release(MOUSE_MIDDLE);
}

void processCommand(const char* cmd) {
    // Parse command type (everything before first ':')
    char type[16];
    int i = 0;
    while (cmd[i] != ':' && cmd[i] != '\0' && i < 15) {
        type[i] = cmd[i];
        i++;
    }
    type[i] = '\0';

    // Skip the ':' separator
    const char* args = (cmd[i] == ':') ? &cmd[i + 1] : "";

    if (strcmp(type, "KEY") == 0) {
        handleKeyPress(args);
    } else if (strcmp(type, "KEYS") == 0) {
        handleKeyString(args);
    } else if (strcmp(type, "SPECIAL") == 0) {
        handleSpecialKey(args);
    } else if (strcmp(type, "MOUSE_MOVE") == 0) {
        handleMouseMove(args);
    } else if (strcmp(type, "MOUSE_CLICK") == 0) {
        handleMouseClick(args);
    } else if (strcmp(type, "MOUSE_DOWN") == 0) {
        handleMouseDown(args);
    } else if (strcmp(type, "MOUSE_UP") == 0) {
        handleMouseUp(args);
    } else if (strcmp(type, "KEY_DOWN") == 0) {
        handleKeyDown(args);
    } else if (strcmp(type, "KEY_UP") == 0) {
        handleKeyUp(args);
    } else if (strcmp(type, "PING") == 0) {
        // Heartbeat / connection test
    } else {
        Serial.println("ERR:UNKNOWN_CMD");
        return;
    }

    Serial.println("OK");
}

// Parse next integer from a colon-separated string, advance pointer
int parseNextInt(const char** ptr) {
    int val = atoi(*ptr);
    // Advance past this value to next ':'
    while (**ptr != ':' && **ptr != '\0') (*ptr)++;
    if (**ptr == ':') (*ptr)++;
    return val;
}

// Parse next char from args
char parseNextChar(const char** ptr) {
    char c = **ptr;
    (*ptr)++;
    if (**ptr == ':') (*ptr)++;
    return c;
}

// KEY:<char>:<hold_ms>
void handleKeyPress(const char* args) {
    const char* p = args;
    char key = parseNextChar(&p);
    int holdMs = parseNextInt(&p);
    if (holdMs < 1) holdMs = 50;

    Keyboard.press(key);
    delay(holdMs);
    Keyboard.release(key);
}

// KEYS:<string>:<hold_ms>
void handleKeyString(const char* args) {
    // Find the last ':' to separate string from hold_ms
    const char* lastColon = strrchr(args, ':');
    int holdMs = 30;
    int strLen;

    if (lastColon != NULL && lastColon != args) {
        holdMs = atoi(lastColon + 1);
        strLen = lastColon - args;
    } else {
        strLen = strlen(args);
    }

    for (int i = 0; i < strLen; i++) {
        Keyboard.press(args[i]);
        delay(holdMs);
        Keyboard.release(args[i]);
        delay(holdMs / 2);
    }
}

// SPECIAL:<keycode>:<hold_ms>
void handleSpecialKey(const char* args) {
    const char* p = args;
    int keycode = parseNextInt(&p);
    int holdMs = parseNextInt(&p);
    if (holdMs < 1) holdMs = 50;

    Keyboard.press(keycode);
    delay(holdMs);
    Keyboard.release(keycode);
}

// MOUSE_MOVE:<dx>:<dy>
void handleMouseMove(const char* args) {
    const char* p = args;
    int dx = parseNextInt(&p);
    int dy = parseNextInt(&p);

    // Clamp to signed 8-bit range
    dx = constrain(dx, -127, 127);
    dy = constrain(dy, -127, 127);

    // Add subtle jitter (+-1) for naturalness
    int jitterX = random(-1, 2);  // -1, 0, or 1
    int jitterY = random(-1, 2);

    // Only apply jitter if the move is large enough
    if (abs(dx) > 3) dx += jitterX;
    if (abs(dy) > 3) dy += jitterY;

    // Re-clamp after jitter
    dx = constrain(dx, -127, 127);
    dy = constrain(dy, -127, 127);

    Mouse.move(dx, dy, 0);
}

// MOUSE_CLICK:<button>:<hold_ms>
void handleMouseClick(const char* args) {
    const char* p = args;
    int button = parseNextInt(&p);
    int holdMs = parseNextInt(&p);
    if (holdMs < 1) holdMs = 50;

    uint8_t btn = (button == 2) ? MOUSE_RIGHT :
                  (button == 3) ? MOUSE_MIDDLE : MOUSE_LEFT;

    Mouse.press(btn);
    delay(holdMs);
    Mouse.release(btn);
}

// MOUSE_DOWN:<button>
void handleMouseDown(const char* args) {
    int button = atoi(args);
    uint8_t btn = (button == 2) ? MOUSE_RIGHT :
                  (button == 3) ? MOUSE_MIDDLE : MOUSE_LEFT;
    Mouse.press(btn);
}

// MOUSE_UP:<button>
void handleMouseUp(const char* args) {
    int button = atoi(args);
    uint8_t btn = (button == 2) ? MOUSE_RIGHT :
                  (button == 3) ? MOUSE_MIDDLE : MOUSE_LEFT;
    Mouse.release(btn);
}

// KEY_DOWN:<char>
void handleKeyDown(const char* args) {
    if (args[0] != '\0') {
        Keyboard.press(args[0]);
    }
}

// KEY_UP:<char>
void handleKeyUp(const char* args) {
    if (args[0] != '\0') {
        Keyboard.release(args[0]);
    }
}
