"""
Standalone validation of resolution scaling logic.
No botty dependencies required - just reads INI and applies math.

Run: python tools/test_resolution_scaling.py
"""
import configparser
import os

RESOLUTION_PRESETS = {
    "720p":  (1280, 720, 1.0),
    "1080p": (1920, 1080, 1.5),
    "1440p": (2560, 1440, 2.0),
    "4k":    (3840, 2160, 3.0),
}

def load_game_ini():
    """Load game.ini values at 720p baseline."""
    parser = configparser.ConfigParser()
    ini_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'game.ini')
    parser.read(ini_path)

    ui_pos = {}
    for key in parser['ui_pos']:
        ui_pos[key] = int(parser['ui_pos'][key])

    ui_roi = {}
    for key in parser['ui_roi']:
        ui_roi[key] = [int(x) for x in parser['ui_roi'][key].split(',')]

    paths = {}
    for key in parser['path']:
        vals = [int(x) for x in parser['path'][key].split(',')]
        paths[key] = [(vals[i], vals[i+1]) for i in range(0, len(vals), 2)]

    return ui_pos, ui_roi, paths


def scale_values(ui_pos, ui_roi, paths, res_name):
    """Apply resolution scaling to a copy of the values."""
    width, height, scale = RESOLUTION_PRESETS[res_name]

    scaled_pos = dict(ui_pos)
    scaled_pos['screen_width'] = width
    scaled_pos['screen_height'] = height
    scaled_pos['center_x'] = width // 2
    scaled_pos['center_y'] = height // 2
    skip = {'screen_width', 'screen_height', 'center_x', 'center_y'}
    for key in scaled_pos:
        if key not in skip:
            scaled_pos[key] = int(ui_pos[key] * scale)

    scaled_roi = {}
    for key in ui_roi:
        scaled_roi[key] = [int(v * scale) for v in ui_roi[key]]

    scaled_paths = {}
    for key in paths:
        scaled_paths[key] = [(int(x * scale), int(y * scale)) for x, y in paths[key]]

    return scaled_pos, scaled_roi, scaled_paths


def main():
    ui_pos, ui_roi, paths = load_game_ini()

    print("=" * 70)
    print("Resolution Scaling Validation")
    print("=" * 70)

    # Show key values at each resolution
    sample_pos_keys = ['screen_width', 'screen_height', 'center_x', 'center_y',
                       'save_and_exit_x', 'save_and_exit_y', 'slot_width',
                       'reached_node_dist', 'item_dist', 'skill_bar_height']
    sample_roi_keys = ['play_btn', 'health_globe', 'mana_globe', 'save_and_exit']
    sample_path_keys = ['pindle_end', 'pindle_safe_dist']

    for res_name, (w, h, s) in RESOLUTION_PRESETS.items():
        if s == 1.0:
            pos, roi, path = ui_pos, ui_roi, paths
        else:
            pos, roi, path = scale_values(ui_pos, ui_roi, paths, res_name)

        print(f"\n--- {res_name} ({w}x{h}, scale={s}x) ---")
        print(f"  UI Positions:")
        for key in sample_pos_keys:
            if key in pos:
                orig = ui_pos[key]
                print(f"    {key:25s} = {pos[key]:6d}  (720p: {orig})")

        print(f"  UI ROIs [left, top, width, height]:")
        for key in sample_roi_keys:
            if key in roi:
                orig = ui_roi[key]
                print(f"    {key:25s} = {str(roi[key]):30s}  (720p: {orig})")

        print(f"  Paths:")
        for key in sample_path_keys:
            if key in path:
                orig = paths[key]
                print(f"    {key:25s} = {path[key]}")
                print(f"    {'':25s}   (720p: {orig})")

    # Validation checks
    print(f"\n{'=' * 70}")
    print("Validation Checks")
    print("=" * 70)
    errors = []

    for res_name, (w, h, s) in RESOLUTION_PRESETS.items():
        if s == 1.0:
            continue
        pos, roi, _ = scale_values(ui_pos, ui_roi, paths, res_name)

        if pos['screen_width'] != w:
            errors.append(f"{res_name}: screen_width={pos['screen_width']}, expected {w}")
        if pos['screen_height'] != h:
            errors.append(f"{res_name}: screen_height={pos['screen_height']}, expected {h}")
        if pos['center_x'] != w // 2:
            errors.append(f"{res_name}: center_x={pos['center_x']}, expected {w // 2}")

        # Check save_and_exit scales correctly
        expected = int(ui_pos['save_and_exit_x'] * s)
        if pos['save_and_exit_x'] != expected:
            errors.append(f"{res_name}: save_and_exit_x={pos['save_and_exit_x']}, expected {expected}")

        # Check ROI scales correctly (all 4 components)
        for roi_key in ['play_btn', 'health_globe']:
            if roi_key in roi:
                for i, component in enumerate(['left', 'top', 'width', 'height']):
                    expected = int(ui_roi[roi_key][i] * s)
                    if roi[roi_key][i] != expected:
                        errors.append(f"{res_name}: {roi_key}[{component}]={roi[roi_key][i]}, expected {expected}")

        # Check proportions: save_and_exit should be near center horizontally
        ratio = pos['save_and_exit_x'] / pos['screen_width']
        baseline_ratio = ui_pos['save_and_exit_x'] / ui_pos['screen_width']
        if abs(ratio - baseline_ratio) > 0.01:
            errors.append(f"{res_name}: save_exit ratio {ratio:.3f} differs from 720p {baseline_ratio:.3f}")

    if errors:
        print(f"\nFAILED ({len(errors)} errors):")
        for e in errors:
            print(f"  X {e}")
    else:
        print(f"\nALL CHECKS PASSED")
        print(f"  - Screen dimensions correct for all resolutions")
        print(f"  - UI positions scale linearly")
        print(f"  - ROI rectangles scale all 4 components")
        print(f"  - Proportional positions preserved across resolutions")

    print("=" * 70)


if __name__ == '__main__':
    main()
