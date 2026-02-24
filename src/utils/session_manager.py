"""
Session Manager - Play time limits, break scheduling, run variance.
Critical for avoiding behavioral detection patterns.
"""

import time
import random
import json
import os
from datetime import datetime
from logger import Logger


class SessionManager:
    """Manages play sessions to appear human-like."""

    def __init__(self, config: dict = None):
        if config is None:
            config = {}
        self.max_daily_hours = config.get('max_daily_hours', 8)
        self.avg_session_minutes = config.get('avg_session_minutes', 150)
        self.session_variance_minutes = config.get('session_variance_minutes', 30)
        self.avg_break_minutes = config.get('avg_break_minutes', 25)
        self.break_variance_minutes = config.get('break_variance_minutes', 10)
        self.skip_loot_probability = config.get('skip_loot_probability', 0.02)
        self.random_action_probability = config.get('random_action_probability', 0.05)

        self.session_length_s = self._gaussian_session_length()
        self.break_length_s = self._gaussian_break_length()

        self.runs_this_session = 0
        self.total_runs_today = 0
        self.session_start = None
        self.daily_start = time.time()
        self.total_play_time_today = 0.0

        self.log_dir = 'log/sessions'
        self._run_log = []

        Logger.info(f"Session planned: {self.session_length_s / 60:.0f}min play, "
                     f"{self.break_length_s / 60:.0f}min break")

    def start_session(self):
        """Mark the beginning of a new play session."""
        self.session_start = time.time()
        self.runs_this_session = 0
        self.session_length_s = self._gaussian_session_length()
        Logger.info(f"Starting session ({self.session_length_s / 60:.0f} minutes)")

    def should_continue_running(self) -> bool:
        """Check if we should do another run."""
        if self.should_stop_for_day():
            return False
        if self.should_take_break():
            return False
        return True

    def should_take_break(self) -> bool:
        """Check if session time has been exceeded."""
        if self.session_start is None:
            return False
        elapsed = time.time() - self.session_start
        return elapsed >= self.session_length_s

    def should_stop_for_day(self) -> bool:
        """Check if daily play limit has been exceeded."""
        total = self.total_play_time_today
        if self.session_start:
            total += time.time() - self.session_start
        max_seconds = self.max_daily_hours * 3600
        return total >= max_seconds

    def should_skip_loot(self) -> bool:
        """Occasionally skip looting for human-like behavior."""
        return random.random() < self.skip_loot_probability

    def should_random_action(self) -> bool:
        """Check if we should do a random human-like action."""
        return random.random() < self.random_action_probability

    def get_break_duration(self) -> float:
        """Return humanized break duration in seconds."""
        return self._gaussian_break_length()

    def end_session(self):
        """Mark the end of a play session."""
        if self.session_start:
            elapsed = time.time() - self.session_start
            self.total_play_time_today += elapsed
            Logger.info(f"Session ended: {elapsed / 60:.0f}min, "
                         f"{self.runs_this_session} runs, "
                         f"total today: {self.total_play_time_today / 60:.0f}min")
        self.session_start = None

    def log_run(self, run_duration: float, items_found: list) -> None:
        """Log a completed run's statistics."""
        self.runs_this_session += 1
        self.total_runs_today += 1

        run_data = {
            'timestamp': datetime.now().isoformat(),
            'run_number': self.total_runs_today,
            'session_run': self.runs_this_session,
            'duration_s': round(run_duration, 2),
            'items': items_found,
        }

        self._run_log.append(run_data)
        Logger.info(f"Run #{self.total_runs_today} complete: {run_duration:.1f}s, "
                     f"{len(items_found)} items found")

    def save_log(self):
        """Save the run log to a JSON file."""
        if not self._run_log:
            return

        os.makedirs(self.log_dir, exist_ok=True)
        date_str = datetime.now().strftime('%Y%m%d')
        log_path = os.path.join(self.log_dir, f'runs_{date_str}.json')

        # Append to existing log if it exists
        existing = []
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        existing.extend(self._run_log)

        with open(log_path, 'w') as f:
            json.dump(existing, f, indent=2)

        Logger.info(f"Saved {len(self._run_log)} run logs to {log_path}")
        self._run_log.clear()

    def get_stats(self) -> dict:
        """Return current session statistics."""
        session_elapsed = 0
        if self.session_start:
            session_elapsed = time.time() - self.session_start

        return {
            'runs_this_session': self.runs_this_session,
            'total_runs_today': self.total_runs_today,
            'session_elapsed_min': session_elapsed / 60,
            'total_play_time_min': (self.total_play_time_today + session_elapsed) / 60,
            'max_daily_min': self.max_daily_hours * 60,
        }

    def _gaussian_session_length(self) -> float:
        """Generate a gaussian-distributed session length in seconds."""
        minutes = random.gauss(self.avg_session_minutes, self.session_variance_minutes)
        minutes = max(30, min(self.avg_session_minutes * 2, minutes))
        return minutes * 60

    def _gaussian_break_length(self) -> float:
        """Generate a gaussian-distributed break length in seconds."""
        minutes = random.gauss(self.avg_break_minutes, self.break_variance_minutes)
        minutes = max(5, min(self.avg_break_minutes * 3, minutes))
        return minutes * 60
