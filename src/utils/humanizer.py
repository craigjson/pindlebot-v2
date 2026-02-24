"""
Humanizer - Makes bot actions appear human-like.
Bezier mouse curves, gaussian timing, position jitter, run variation.
This is the most critical module for avoiding detection.
"""

import math
import random
import time
from logger import Logger

# Action delay profiles: (base_ms, variance_ms)
ACTION_DELAYS = {
    'click': (115, 35),
    'between_casts': (350, 100),
    'after_portal': (1000, 300),
    'before_loot': (550, 150),
    'between_pickups': (275, 80),
    'menu_interaction': (400, 120),
    'game_creation': (5000, 2000),
    'after_load': (800, 300),
    'before_combat': (400, 200),
    'skill_select': (150, 50),
}


class Humanizer:
    """All humanization utilities for making bot actions appear natural."""

    # --- Timing ---

    @staticmethod
    def delay(base_ms: float, variance_ms: float = 100) -> None:
        """Gaussian-distributed delay. Never below 30ms floor."""
        delay_ms = random.gauss(base_ms, variance_ms)
        delay_ms = max(30, delay_ms)
        time.sleep(delay_ms / 1000.0)

    @staticmethod
    def action_delay(action_type: str) -> None:
        """Context-aware delay based on action type."""
        if action_type in ACTION_DELAYS:
            base, variance = ACTION_DELAYS[action_type]
        else:
            base, variance = (200, 50)
            Logger.debug(f"Unknown action type '{action_type}', using default delay")

        delay_ms = random.gauss(base, variance)
        delay_ms = max(30, delay_ms)
        time.sleep(delay_ms / 1000.0)

    # --- Mouse Movement ---

    @staticmethod
    def bezier_points(start: tuple, end: tuple, num_points: int = None) -> list:
        """Generate points along a Bezier curve from start to end.

        Uses 1-2 random control points offset from the straight line
        to create natural-looking mouse movement arcs.

        Args:
            start: (x, y) starting position
            end: (x, y) ending position
            num_points: Number of points to generate. If None, scales with distance.

        Returns:
            List of (x, y) integer points along the curve.
        """
        sx, sy = start
        ex, ey = end
        distance = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)

        if distance < 5:
            return [end]

        if num_points is None:
            # Scale points with distance: more points for longer moves
            num_points = max(15, int(distance / 5))
            num_points = min(num_points, 100)

        # Direction vector and perpendicular
        dx = ex - sx
        dy = ey - sy
        # Perpendicular vector (normalized)
        perp_len = max(distance, 1)
        perp_x = -dy / perp_len
        perp_y = dx / perp_len

        # Random offset magnitude (10-35% of distance)
        offset_ratio = random.uniform(0.10, 0.35)
        offset = distance * offset_ratio

        # Decide between quadratic (1 control point) or cubic (2 control points)
        use_cubic = distance > 200 or random.random() < 0.3

        if use_cubic:
            # Two control points at ~33% and ~66% along the line
            t1, t2 = 0.25 + random.uniform(-0.1, 0.1), 0.75 + random.uniform(-0.1, 0.1)
            # Offset in perpendicular direction (same or opposite sides)
            side1 = random.choice([-1, 1])
            side2 = side1 if random.random() < 0.6 else -side1

            cp1 = (
                sx + dx * t1 + perp_x * offset * side1 * random.uniform(0.5, 1.5),
                sy + dy * t1 + perp_y * offset * side1 * random.uniform(0.5, 1.5),
            )
            cp2 = (
                sx + dx * t2 + perp_x * offset * side2 * random.uniform(0.3, 1.0),
                sy + dy * t2 + perp_y * offset * side2 * random.uniform(0.3, 1.0),
            )

            points = []
            for i in range(num_points + 1):
                t = i / num_points
                # Cubic Bezier formula
                u = 1 - t
                x = u**3 * sx + 3 * u**2 * t * cp1[0] + 3 * u * t**2 * cp2[0] + t**3 * ex
                y = u**3 * sy + 3 * u**2 * t * cp1[1] + 3 * u * t**2 * cp2[1] + t**3 * ey
                # Add gaussian noise
                noise_scale = max(1, distance * 0.003)
                x += random.gauss(0, noise_scale)
                y += random.gauss(0, noise_scale)
                points.append((int(round(x)), int(round(y))))
        else:
            # Quadratic: one control point at ~50%
            t_cp = 0.5 + random.uniform(-0.15, 0.15)
            side = random.choice([-1, 1])
            cp = (
                sx + dx * t_cp + perp_x * offset * side * random.uniform(0.7, 1.3),
                sy + dy * t_cp + perp_y * offset * side * random.uniform(0.7, 1.3),
            )

            points = []
            for i in range(num_points + 1):
                t = i / num_points
                u = 1 - t
                x = u**2 * sx + 2 * u * t * cp[0] + t**2 * ex
                y = u**2 * sy + 2 * u * t * cp[1] + t**2 * ey
                noise_scale = max(1, distance * 0.003)
                x += random.gauss(0, noise_scale)
                y += random.gauss(0, noise_scale)
                points.append((int(round(x)), int(round(y))))

        # Ensure the last point is exactly the target
        points[-1] = (int(round(ex)), int(round(ey)))
        return points

    @staticmethod
    def jitter_position(x: int, y: int, radius: float = 3.0) -> tuple:
        """Add gaussian jitter to a click target position."""
        jx = int(round(random.gauss(0, radius / 2)))
        jy = int(round(random.gauss(0, radius / 2)))
        return (x + jx, y + jy)

    # --- Run Variation ---

    @staticmethod
    def vary_cast_count(base: int = 4, min_val: int = 3, max_val: int = 6) -> int:
        """Randomize number of casts per attack sequence."""
        count = int(round(random.gauss(base, 0.8)))
        return max(min_val, min(max_val, count))

    @staticmethod
    def should_do_random_action(probability: float = 0.05) -> bool:
        """Returns True with the given probability for random human-like actions."""
        return random.random() < probability

    @staticmethod
    def vary_path(waypoints: list, max_offset: int = 15) -> list:
        """Add small random offsets to navigation waypoints."""
        varied = []
        for x, y in waypoints:
            ox = random.randint(-max_offset, max_offset)
            oy = random.randint(-max_offset, max_offset)
            varied.append((x + ox, y + oy))
        return varied

    @staticmethod
    def random_pause():
        """Simulate a short human pause (like checking phone)."""
        pause_ms = random.gauss(2000, 500)
        pause_ms = max(500, min(4000, pause_ms))
        Logger.debug(f"Random human pause: {pause_ms:.0f}ms")
        time.sleep(pause_ms / 1000.0)

    @staticmethod
    def get_mouse_move_delay(distance: float) -> float:
        """Get appropriate delay between mouse move steps based on total distance.
        Returns delay in seconds. Simulates variable mouse speed."""
        base_delay = 0.001 + random.uniform(0, 0.003)
        return base_delay
