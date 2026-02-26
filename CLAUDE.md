# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python pixelbot for Diablo 2 Resurrected (D2R). It uses computer vision (template matching, OCR) and input automation to farm bosses, manage inventory, handle town tasks, and run full game sessions autonomously. The bot operates against a 720p D2R window (resolution-scaled automatically).

## Running / developing

```bash
# Activate the virtualenv (Windows)
.venv\Scripts\activate

# Run the bot
python src/main.py

# Run all tests
pytest -s -v

# Run a single test file
pytest test/smoke_test.py

# Build release .exe
python build.py x.x.x
```

Most `src/` modules can also be run directly for isolated testing — they contain `if __name__ == "__main__":` blocks that bind F11 to start and F12 to force-quit, and operate against the live D2R window.

## Project structure

```
config/          params.ini + game.ini + custom.ini overrides
assets/
  templates/     CV template images for UI detection, pathing nodes
  items/         Item name screenshot templates for pickit
  npc/           NPC pose templates
src/
  main.py        Entry point; spawns 3 threads: bot, health_manager, death_manager
  bot.py         State machine (transitions lib) — the top-level run loop
  config.py      Singleton Config; reads params.ini / game.ini / custom.ini
  screen.py      Screen capture, coordinate conversion helpers
  template_finder.py  CV template matching against the live screen
  pather.py      Node-based pathfinding and traversal (walk/teleport)
  char/          Character implementations (inherit from IChar)
  run/           One file per farmable target (Pindle, Trav, Nihlathak, etc.)
  town/          Per-act town navigation (A1–A5) and TownManager
  inventory/     Personal inventory, belt, stash, vendor management
  item/          Pickit logic and consumable tracking
  d2r_image/     OCR pipeline (EasyOCR primary, pytesseract fallback), item parsing, BNIP data
  bnip/          NIP filter language transpiler / evaluator
  ui/            Screen-object detection helpers (meters, skills, loading, etc.)
  utils/
    custom_mouse.py   Mouse abstraction: routes through Arduino HID or software fallback
    arduino_hid.py    Serial interface to Arduino Leonardo/Pro Micro for real USB HID
    arduino_keyboard.py  Keyboard commands via Arduino
    humanizer.py      Bezier mouse curves, gaussian timing jitter
    run_timer.py      Per-phase timing singleton (logs breakdown after each run)
    misc.py           Common utilities: wait(), coordinate transforms, color_filter, etc.
  messages/      Discord webhook notifications
test/            Mirrors src/ structure; pytest-based
```

## Architecture: how the bot works

**Threading model** (`main.py`): Three threads run in parallel:
1. **`bot.py`** — main state machine driving the run loop
2. **`health_manager.py`** — monitors HP/MP bar and triggers chicken (exit game) or potion use
3. **`death_manager.py`** — monitors for death screen and kills/restarts the bot thread

The `health_manager` is paused during town (safe) and unpaused during combat via `set_pause_state()`.

**State machine** (`bot.py`): Uses the `transitions` library. States: `initialization → hero_selection → town → [pindle/shenk/trav/nihlathak/arcane/diablo] → town → … → end_game → initialization`. All implementation lives in manager classes; `bot.py` just orchestrates transitions and calls `.approach()` / `.battle()` on run objects.

**Coordinate systems** (critical when reading/writing position code):
- **Monitor**: origin top-left of first monitor
- **Screen**: origin top-left of D2R window
- **Absolute**: origin at screen center (character footpoint)
- **Relative**: relative to a matched template

Conversion functions in `screen.py`: `convert_screen_to_abs`, `convert_abs_to_monitor`, `convert_monitor_to_screen`, etc.

**Character system**: All character builds inherit from `IChar` (`src/char/i_char.py`). Each build must implement `kill_pindle()`, `kill_shenk()`, `kill_nihlathak()`, etc. for the bosses it supports. `CharacterCapabilities` (discovered at game start) tracks whether the char can teleport natively or via charges.

**Run pattern**: Each farmable run is a class with two methods:
- `approach(start_loc)` — navigate from town to the encounter start
- `battle(do_pre_buff)` — fight, loot, return `(end_location, picked_up_items)` or `False` on failure

**Input layer**: `utils/custom_mouse.py` is the unified mouse API imported everywhere. It transparently routes to Arduino HID (real USB device, harder to detect) when connected, or falls back to the software `mouse` library. `utils/humanizer.py` adds Bezier curves and gaussian timing. `utils/arduino_keyboard.py` does the same for keyboard.

**Image processing pipeline**: Ground loot detection uses color-based cluster segmentation (`processing_helpers.py`) then OCR. Tooltip parsing uses EasyOCR with a custom model. Results go through the BNIP filter engine (`bnip/transpile.py`) to decide pick/keep/sell.

**Configuration**: `Config()` is a singleton backed by `config/params.ini` + `config/game.ini`. UI coordinates in `game.ini` are authored at 720p and auto-scaled to the configured resolution. Override any param in `config/custom.ini` without modifying `params.ini`.

## Key conventions

- `wait(min, max)` from `utils/misc.py` is used for all delays (random between min and max seconds).
- Template names (uppercase strings like `"PINDLE_0"`) map to files in `assets/templates/`.
- `Location` is an enum in `pather.py`; node IDs are integers referencing pathfinding node data.
- `ScreenObjects` in `ui_manager.py` is the registry of named UI elements for `is_visible()` / `detect_screen_object()`.
- `RunTimer.get()` is a singleton for per-phase timing. Wrap phases with `t.start("name")` / `t.stop("name")`.
- Adding a new run: create `src/run/myrun.py` with `approach()` + `battle()`, wire it in `bot.py` `__init__` and state machine, add to `params.ini` `[routes]` docs.
- Adding a new character: subclass `IChar` or an existing character base (e.g. `Sorceress`), implement the kill methods needed, register in `bot.py`'s `match` block.
