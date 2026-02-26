import time
from collections import defaultdict
from logger import Logger


class RunTimer:
    """Tracks timing for each phase of a bot run. Singleton so any module can access it."""
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._active = {}  # phase_name -> start_time
        self._current_run = {}  # phase_name -> cumulative duration this run
        self._history = defaultdict(list)  # phase_name -> [durations across runs]
        self._run_start = None
        self._phase_order = []  # track insertion order for display

    def start_run(self):
        """Call at the beginning of each run."""
        if self._current_run:
            self._flush_run()
        self._current_run = {}
        self._active = {}
        self._phase_order = []
        self._run_start = time.time()

    def start(self, phase: str):
        """Start timing a named phase."""
        self._active[phase] = time.time()

    def stop(self, phase: str) -> float:
        """Stop timing a phase. Returns its duration."""
        if phase not in self._active:
            return 0
        duration = time.time() - self._active.pop(phase)
        self._current_run[phase] = self._current_run.get(phase, 0) + duration
        if phase not in self._phase_order:
            self._phase_order.append(phase)
        return duration

    def end_run(self):
        """Call at end of run. Logs current run breakdown + running averages."""
        if self._run_start is None:
            return
        total = time.time() - self._run_start
        self._current_run["_total"] = total
        self._flush_run()
        self._log_summary()
        self._run_start = None

    def _flush_run(self):
        for phase, duration in self._current_run.items():
            self._history[phase].append(duration)
        self._current_run = {}

    def _log_summary(self):
        if not self._history.get("_total"):
            return
        n_runs = len(self._history["_total"])
        last_total = self._history["_total"][-1]
        avg_total = sum(self._history["_total"]) / n_runs

        lines = [
            f"=== Run #{n_runs} timing (total: {last_total:.1f}s, avg: {avg_total:.1f}s) ==="
        ]
        # Show phases in the order they were recorded
        tracked_time = 0
        for phase in self._phase_order:
            if phase.startswith("_"):
                continue
            vals = self._history[phase]
            last = vals[-1] if vals else 0
            avg = sum(vals) / len(vals) if vals else 0
            pct = (last / last_total * 100) if last_total > 0 else 0
            lines.append(f"  {phase:.<30s} {last:5.1f}s ({pct:4.1f}%) avg={avg:.1f}s")
            tracked_time += last
        untracked = last_total - tracked_time
        if untracked > 0.5:
            pct = (untracked / last_total * 100) if last_total > 0 else 0
            lines.append(f"  {'(untracked)':.<30s} {untracked:5.1f}s ({pct:4.1f}%)")
        Logger.info("\n".join(lines))
