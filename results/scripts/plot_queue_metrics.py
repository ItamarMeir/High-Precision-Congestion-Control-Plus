#!/usr/bin/env python3
"""Generate queue-related plots from qlen/pfc outputs.

Outputs:
- switch_queue_analysis.png: combined queue length + CDF + INT overlay
- pfc_pause.png: PFC pause events vs time (binned)
"""
import argparse
import csv
import os
from collections import defaultdict
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt


def _parse_qlen_blocks(qlen_file: str) -> List[Tuple[int, Dict[Tuple[int, int], List[int]]]]:
    """Parse qlen file blocks.

    Format:
      time: <nanoseconds>
      <switch_id> <port_idx> <cnt0> <cnt1> ...
    """
    blocks = []
    current_time = None
    current = {}
    with open(qlen_file, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("time:"):
                if current_time is not None:
                    blocks.append((current_time, current))
                current_time = int(line.split(":", 1)[1].strip())
                current = {}
                continue
            parts = line.split()
            if len(parts) < 3 or current_time is None:
                continue
            try:
                sw_id = int(parts[0])
                port = int(parts[1])
                counts = [int(x) for x in parts[2:]]
                current[(sw_id, port)] = counts
            except ValueError:
                continue
    if current_time is not None:
        blocks.append((current_time, current))
    return blocks


def _avg_qlen_over_time(blocks: List[Tuple[int, Dict[Tuple[int, int], List[int]]]]):
    """Compute the maximum average queue length across any single port at each timestep."""
    times = []
    avgs = []
    for ts, dist_by_port in blocks:
        max_port_avg = 0.0
        for _, counts in dist_by_port.items():
            total_samples = 0
            total_bytes = 0
            for kb, cnt in enumerate(counts):
                if cnt <= 0:
                    continue
                total_samples += cnt
                total_bytes += cnt * kb * 1000
            
            if total_samples > 0:
                port_avg = total_bytes / total_samples
                if port_avg > max_port_avg:
                    max_port_avg = port_avg
                    
        times.append(ts / 1e9)
        avgs.append(max_port_avg)

    if times:
        t0 = times[0]
        times = [max(0.0, t - t0) for t in times]
    return times, avgs


def _cdf_from_blocks(blocks: List[Tuple[int, Dict[Tuple[int, int], List[int]]]]):
    if not blocks:
        return [], []
    max_len = 0
    for _, dist_by_port in blocks:
        for counts in dist_by_port.values():
            if len(counts) > max_len:
                max_len = len(counts)
    if max_len == 0:
        return [], []
    agg = [0] * max_len
    for _, dist_by_port in blocks:
        for counts in dist_by_port.values():
            for i, cnt in enumerate(counts):
                agg[i] += cnt
    total = sum(agg)
    if total == 0:
        return [], []
    xs = []
    ys = []
    cumulative = 0
    for kb, cnt in enumerate(agg):
        if cnt < 0:
            continue
        cumulative += cnt
        xs.append(kb)
        y = 100.0 * cumulative / total
        if y < 0:
            y = 0.0
        elif y > 100:
            y = 100.0
        ys.append(y)
        if cumulative >= total:
            break
    return xs, ys


def _cdf_from_avg(avgs: List[float]):
    if not avgs:
        return [], []
    xs = sorted(avgs)
    n = len(xs)
    ys = [100.0 * (i + 1) / n for i in range(n)]
    return xs, ys



from pathlib import Path


def _parse_int_hop_metadata(config_file):
    """Return metadata needed to separate switch INT hops from the HPCC+ host hop."""
    meta = {"cc_mode": None, "switch_hops": None}
    if not config_file or not Path(config_file).exists():
        return meta

    with open(config_file, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if not parts:
                continue
            key = parts[0]
            if key == 'CC_MODE' and len(parts) > 1:
                try:
                    meta['cc_mode'] = int(parts[1])
                except ValueError:
                    pass
            elif key == 'INT_MULTI' and len(parts) > 1:
                try:
                    meta['switch_hops'] = int(parts[1])
                except ValueError:
                    pass
    return meta

def _parse_schedules(config_file):
    """Parse config file to extract RX_PULL_RATE_SCHEDULE."""
    schedules = {}
    if not config_file or not Path(config_file).exists():
        return schedules
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'): continue
            if 'RX_PULL_RATE_SCHEDULE' in line:
                parts = line.split()
                if len(parts) >= 3 and parts[0] == 'RX_PULL_RATE_SCHEDULE':
                    try:
                        node_id = int(parts[1])
                        count = int(parts[2])
                        schedule = []
                        idx = 3
                        for _ in range(count):
                            if idx + 1 < len(parts):
                                t = float(parts[idx])
                                r = float(parts[idx+1])
                                schedule.append((t, r))
                                idx += 2
                        schedules[node_id] = schedule
                    except ValueError: pass
    return schedules

def _draw_lines(ax, schedules):
    # determine y-limit to place text
    ylim = ax.get_ylim()
    ymax = ylim[1]
    for node_id, schedule in schedules.items():
            for time, rate in schedule:
                ax.axvline(x=time, color='gray', linestyle=':', alpha=0.8, linewidth=1.5)
                # Use strict format: t=<time>s Rate=<rate>
                ax.text(time, ymax * 0.98, f' t={time}s\nRate={rate}', rotation=90, 
                        verticalalignment='top', fontsize=8, color='black', alpha=0.7)


def _parse_queue_depth_csv(csv_path, allowed_hops=None):
    """Parse queue_depth.csv (INT per-packet data) and return time-binned max Qlen.

    Returns (times_s, max_qlen_bytes) aggregated into 1ms bins.
    """
    if not csv_path or not os.path.exists(csv_path):
        return [], []

    raw = defaultdict(int)  # bin_index -> max qlen in that bin
    bin_s = 0.001  # 1ms bins
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            try:
                t = float(row[0])
                hop = int(row[2])
                if allowed_hops is not None and hop not in allowed_hops:
                    continue
                qlen = int(row[3])
                b = int(t / bin_s)
                if qlen > raw[b]:
                    raw[b] = qlen
            except (ValueError, IndexError):
                continue

    if not raw:
        return [], []

    min_b = min(raw.keys())
    max_b = max(raw.keys())
    times = []
    vals = []
    for b in range(min_b, max_b + 1):
        times.append(b * bin_s)
        vals.append(raw.get(b, 0))
    return times, vals


def _plot_avg_qlen(times, avgs, ax=None, out_path=None, schedules=None):
    if ax is None:
        plt.figure(figsize=(10, 4))
        ax = plt.gca()
        should_save = True
    else:
        should_save = False

    ax.plot(times, avgs, linewidth=1.2, marker="o", markersize=3)
    
    if schedules:
        _draw_lines(ax, schedules)

    if times and avgs:
        min_idx = min(range(len(avgs)), key=lambda i: avgs[i])
        max_idx = max(range(len(avgs)), key=lambda i: avgs[i])
        last_idx = len(avgs) - 1
        extra = 3
        if len(times) <= 3:
            extra = 0
        step = max(1, (len(times) - 1) // (extra + 1)) if extra > 0 else None
        extra_idxs = []
        if step:
            extra_idxs = [i for i in range(step, len(times) - 1, step)][:extra]
        label_idxs = sorted(set([min_idx, max_idx, last_idx] + extra_idxs))

        for i in label_idxs:
            t, v = times[i], avgs[i]
            ax.annotate(f"{v:.0f}", xy=(t, v), xytext=(0, 6), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7, color="#333333")

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Queue length (bytes)")
    ax.set_title("Maximum Switch Port Queue Length")
    ax.grid(True, alpha=0.3)

    if should_save and out_path:
        plt.tight_layout()
        plt.savefig(out_path, dpi=150)
        plt.close()


def _plot_int_queue_depth(int_times, int_qlen, out_path, schedules=None, clip_bytes=250, x_max=4.0):
    """Standalone INT queue depth plot, clipped to clip_bytes, x-axis to x_max."""
    if not int_times or not int_qlen:
        return

    fig, ax = plt.subplots(figsize=(14, 5))

    # Clip values above threshold
    clipped = [min(v, clip_bytes) for v in int_qlen]

    ax.fill_between(int_times, clipped,
                    alpha=0.3, color="#e74c3c", step="post")
    ax.plot(int_times, clipped,
            color="#c0392b", linewidth=0.8, drawstyle="steps-post")

    if schedules:
        _draw_lines(ax, schedules)

    ax.set_xlim(min(int_times), x_max)
    ax.set_ylim(0, clip_bytes)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Queue Depth (bytes)")
    ax.set_title(f"Switch Queue Depth (clipped at {clip_bytes} B)")
    ax.grid(True, alpha=0.3)
    # Finer time ticks
    import numpy as np
    ax.set_xticks(np.arange(min(int_times), x_max + 0.1, 0.1))
    ax.tick_params(axis='x', labelsize=7, rotation=45)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"INT queue depth plot saved to: {out_path}")


def _plot_cdf(xs, ys, ax=None, out_path=None, title="Queue Length CDF"):
    if ax is None:
        plt.figure(figsize=(8, 4))
        ax = plt.gca()
        should_save = True
    else:
        should_save = False

    ax.plot(xs, ys, linewidth=1.5)
    ax.set_xlabel("Queue length (B)")
    ax.set_ylabel("CDF (%)")
    ax.set_title(title)
    ax.set_ylim(0, 100)
    # Scale x-axis to actual max value in data, with 5% padding
    if xs:
        max_x = max(xs)
        ax.set_xlim(0, max_x * 1.05)
    else:
        ax.set_xlim(0, 100)
    ax.grid(True, alpha=0.3)

    if should_save and out_path:
        plt.tight_layout()
        plt.savefig(out_path, dpi=150)
        plt.close()


def _plot_pfc(pfc_file: str, out_path: str, bin_us: int):
    bin_ns = bin_us * 1000
    bins = {}
    min_time = None
    with open(pfc_file, "r") as f:
        for raw in f:
            parts = raw.strip().split()
            if len(parts) < 5:
                continue
            try:
                t_ns = int(parts[0])
                event_type = int(parts[4])
            except ValueError:
                continue
            if event_type != 1:
                continue  # pause only
            if min_time is None or t_ns < min_time:
                min_time = t_ns
            b = t_ns // bin_ns
            bins[b] = bins.get(b, 0) + 1

    if not bins:
        plt.figure(figsize=(8, 4))
        plt.title("PFC Pause Events Over Time")
        plt.xlabel("Time (s)")
        plt.ylabel("Pause events per bin")
        plt.text(0.5, 0.5, "No pause events found", ha="center", va="center")
        plt.tight_layout()
        plt.savefig(out_path, dpi=150)
        plt.close()
        return

    xs = sorted(bins.keys())
    ys = [bins[x] for x in xs]
    base = 0 if min_time is None else (min_time // bin_ns)
    times = [max(0.0, (x - base) * bin_ns / 1e9) for x in xs]

    plt.figure(figsize=(10, 4))
    plt.step(times, ys, where="post")
    plt.xlabel("Time (s)")
    plt.ylabel(f"Pause events per {bin_us} us")
    plt.title("PFC Pause Events Over Time")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Plot queue metrics (avg qlen, CDF, PFC pauses)")
    parser.add_argument("--qlen", default="simulation/mix/outputs/qlen/qlen.txt", help="Path to qlen output file")
    parser.add_argument("--pfc", default="simulation/mix/outputs/pfc/pfc.txt", help="Path to pfc output file")
    parser.add_argument("--out-dir", default="simulation/mix/outputs", help="Directory to write plots")
    parser.add_argument("--bin-us", type=int, default=1000, help="Bin size for PFC pause events in microseconds")
    parser.add_argument("--config", default=None, help="Path to config file (for schedule)")
    parser.add_argument("--queue-depth-csv", default=None, help="Path to queue_depth.csv (INT per-packet data)")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    
    schedules = {}
    hop_meta = {"cc_mode": None, "switch_hops": None}
    if args.config:
        schedules = _parse_schedules(args.config)
        hop_meta = _parse_int_hop_metadata(args.config)

    # Fallback to global simulation/queue_depth.csv if not provided or missing
    q_csv = args.queue_depth_csv
    if q_csv is None or not os.path.exists(q_csv):
        # Infer root from script location
        script_dir = Path(__file__).parent.resolve()
        root_dir = script_dir.parent.parent
        fallback_csv = root_dir / "simulation" / "queue_depth.csv"
        if fallback_csv.exists():
            q_csv = str(fallback_csv)
            print(f"Using fallback global queue depth CSV: {q_csv}")

    # Parse INT queue depth CSV
    allowed_hops = None
    if hop_meta.get("cc_mode") == 11 and hop_meta.get("switch_hops") is not None:
        # In HPCC+, the receiver host hop is appended after all switch hops.
        # Keep only the original switch-hop indices for plots labeled as switch depth.
        allowed_hops = set(range(hop_meta["switch_hops"]))

    int_times, int_qlen = _parse_queue_depth_csv(q_csv, allowed_hops=allowed_hops)

    # Prioritize INT queue depth data for the new CDF analysis
    if int_times and int_qlen:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))
        
        # Plot 1: Time-series INT Depth with Schedule Lines
        # Use a higher resolution for the time-series panel
        ax1.fill_between(int_times, int_qlen, alpha=0.3, color="#e74c3c", step="post")
        ax1.plot(int_times, int_qlen, color="#c0392b", linewidth=0.8, drawstyle="steps-post")
        
        if schedules:
            _draw_lines(ax1, schedules)
            
        ax1.set_xlabel("Time (s)")
        ax1.set_ylabel("Queue Depth (bytes)")
        ax1.set_title("Switch Queue Depth (INT Data)")
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: CDF of INT Data
        xs_cdf, ys_cdf = _cdf_from_avg(int_qlen) # Reuse cdf_from_avg on list of values
        _plot_cdf(xs_cdf, ys_cdf, ax=ax2, title="Switch Queue Depth CDF (INT Data)")
        
        plt.tight_layout()
        cdf_path = os.path.join(args.out_dir, "switch_queue_depth_cdf.png")
        plt.savefig(cdf_path, dpi=150)
        plt.close()
        print(f"Switch queue depth CDF plot saved to: {cdf_path}")

    # Keep PFC plot logic
    if os.path.exists(args.pfc):
        _plot_pfc(args.pfc, os.path.join(args.out_dir, "pfc_pause.png"), args.bin_us)
    else:
        print("pfc file not found:", args.pfc)


if __name__ == "__main__":
    main()
