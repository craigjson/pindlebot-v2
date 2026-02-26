"""
Analyze bot run timing data from log/timing/timing.jsonl.

Usage:
    python analyze_timing.py                  # read default log file
    python analyze_timing.py path/to/file     # read specific file
    python analyze_timing.py --last N         # only analyze last N runs
    python analyze_timing.py --outlier 2.0    # set outlier z-score threshold (default 2.5)
"""

import json
import os
import sys
import statistics
from datetime import datetime


DEFAULT_PATH = "log/timing/timing.jsonl"
DEFAULT_OUTLIER_Z = 2.5
HIGH_VARIANCE_CV = 0.4  # coefficient of variation threshold for flagging noisy phases


def load_records(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"No timing data found at {path}")
        print("Run the bot first — data is written after each run.")
        sys.exit(0)
    records = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Warning: skipping malformed record on line {i}: {e}")
    return records


def fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(len(sorted_vals) * p)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def analyze(records: list[dict], outlier_z: float):
    n = len(records)
    print(f"\n=== Phase Timing Summary (N={n} runs) ===")
    print(f"{'Phase':<32s} {'count':>5s}  {'mean':>6s}  {'p50':>6s}  {'p90':>6s}  {'max':>6s}  {'cv':>5s}  note")
    print("-" * 82)

    # Collect values per phase
    phase_data: dict[str, list[float]] = {}
    for record in records:
        for phase, duration in record.get("phases", {}).items():
            phase_data.setdefault(phase, []).append(duration)

    # Sort by mean duration descending (biggest time sinks first)
    phase_stats: dict[str, tuple] = {}
    rows = []
    for phase, vals in phase_data.items():
        if len(vals) == 0:
            continue
        mean = statistics.mean(vals)
        stdev = statistics.stdev(vals) if len(vals) > 1 else 0.0
        sv = sorted(vals)
        p50 = percentile(sv, 0.5)
        p90 = percentile(sv, 0.9)
        mx = sv[-1]
        cv = stdev / mean if mean > 0 else 0.0
        phase_stats[phase] = (mean, stdev)
        note = "HIGH VARIANCE" if cv > HIGH_VARIANCE_CV else ""
        rows.append((mean, phase, len(vals), mean, p50, p90, mx, cv, note))

    rows.sort(key=lambda r: r[0], reverse=True)
    for _, phase, count, mean, p50, p90, mx, cv, note in rows:
        print(f"  {phase:<30s} {count:>5d}  {mean:>5.1f}s  {p50:>5.1f}s  {p90:>5.1f}s  {mx:>5.1f}s  {cv:>4.2f}  {note}")

    # Total row
    total_vals = [r.get("total", 0) for r in records if "total" in r]
    if total_vals:
        mean_t = statistics.mean(total_vals)
        sv_t = sorted(total_vals)
        p50_t = percentile(sv_t, 0.5)
        p90_t = percentile(sv_t, 0.9)
        mx_t = sv_t[-1]
        cv_t = (statistics.stdev(total_vals) / mean_t) if len(total_vals) > 1 and mean_t > 0 else 0.0
        print("-" * 82)
        print(f"  {'TOTAL (full cycle)':<30s} {len(total_vals):>5d}  {mean_t:>5.1f}s  {p50_t:>5.1f}s  {p90_t:>5.1f}s  {mx_t:>5.1f}s  {cv_t:>4.2f}")

    # Outlier detection
    if len(records) < 5:
        print(f"\n(Need at least 5 runs for outlier detection, have {n})")
        return

    print(f"\n=== Outlier Runs (phase > mean + {outlier_z}σ) ===")
    found_outliers = False
    for i, record in enumerate(records):
        ts_str = fmt_ts(record["ts"]) if "ts" in record else f"run #{i+1}"
        run_outliers = []
        for phase, duration in record.get("phases", {}).items():
            if phase not in phase_stats:
                continue
            mean, stdev = phase_stats[phase]
            if stdev > 0:
                z = (duration - mean) / stdev
                if z >= outlier_z:
                    run_outliers.append((z, phase, duration, mean))
        if run_outliers:
            found_outliers = True
            run_outliers.sort(key=lambda x: x[0], reverse=True)
            for z, phase, duration, mean in run_outliers:
                print(f"  Run #{i+1:4d}  {ts_str}  {phase}: {duration:.1f}s  (avg={mean:.1f}s, z={z:.1f})")
    if not found_outliers:
        print(f"  None found (all phases within {outlier_z}σ of their mean)")

    # Most variable phases (potential instability sources)
    noisy = [(cv, phase) for _, phase, _, mean, _, _, _, cv, _ in rows if cv > HIGH_VARIANCE_CV]
    if noisy:
        noisy.sort(reverse=True)
        print(f"\n=== High-Variance Phases (cv > {HIGH_VARIANCE_CV}) — likely instability sources ===")
        for cv, phase in noisy:
            vals = phase_data[phase]
            mn, mx = min(vals), max(vals)
            print(f"  {phase:<32s} cv={cv:.2f}  range=[{mn:.1f}s, {mx:.1f}s]")


def main():
    args = sys.argv[1:]
    path = DEFAULT_PATH
    outlier_z = DEFAULT_OUTLIER_Z
    last_n = None

    i = 0
    while i < len(args):
        if args[i] == "--last" and i + 1 < len(args):
            last_n = int(args[i + 1])
            i += 2
        elif args[i] == "--outlier" and i + 1 < len(args):
            outlier_z = float(args[i + 1])
            i += 2
        else:
            path = args[i]
            i += 1

    records = load_records(path)
    print(f"Loaded {len(records)} runs from {path}")

    if last_n is not None and last_n < len(records):
        print(f"Analyzing last {last_n} runs only")
        records = records[-last_n:]

    analyze(records, outlier_z)


if __name__ == "__main__":
    main()
