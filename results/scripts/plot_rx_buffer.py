#!/usr/bin/env python3
"""Plot NIC RX buffer occupancy over time.

Input format (per line):
<time_ns> <node_id> <if_index> <bytes>
"""
import argparse
import sys
import os
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


def parse_config(config_file):
    """Parse config file and extract RX buffer settings and receiver nodes."""
    config = {
        "rx_buffer_size": None,
        "rx_buffer_per_queue": None,
        "receiver_nodes": set(),
        "flow_file": None,
        "exp_name": None,
        "flow_start_times": [],
    }
    if not config_file or not os.path.exists(config_file):
        return config

    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            if parts[0] == 'RX_BUFFER_SIZE':
                try:
                    config["rx_buffer_size"] = int(parts[1])
                except ValueError:
                    pass
            elif parts[0] == 'RX_BUFFER_PER_QUEUE':
                try:
                    config["rx_buffer_per_queue"] = int(parts[1])
                except ValueError:
                    pass
            elif parts[0] == 'RX_PULL_MODE_NODE' and len(parts) >= 3:
                try:
                    node_id = int(parts[1])
                    pull_mode = int(parts[2])
                    if pull_mode == 1:
                        config["receiver_nodes"].add(node_id)
                except ValueError:
                    pass
            elif parts[0] == 'FLOW_FILE':
                config["flow_file"] = parts[1]
            elif parts[0] == 'EXP_NAME':
                config["exp_name"] = parts[1]

    if not config["receiver_nodes"] and config["flow_file"]:
        flow_path = _resolve_relative_path(config_file, config["flow_file"])
        if flow_path and flow_path.exists():
            config["receiver_nodes"] = _parse_flow_receivers(flow_path)

    if config["flow_file"]:
        flow_path = _resolve_relative_path(config_file, config["flow_file"])
        if flow_path and flow_path.exists():
            config["flow_start_times"] = _parse_flow_start_times(flow_path)

    return config


def _resolve_relative_path(config_file, path_str):
    path = Path(path_str)
    if path.is_absolute():
        return path

    # Support both config-relative and repo-relative conventions used across cases.
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        (Path(config_file).parent / path).resolve(),
        (Path.cwd() / path).resolve(),
        (repo_root / path).resolve(),
        (repo_root / "simulation" / path).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _parse_flow_receivers(flow_path):
    receivers = set()
    with open(flow_path, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    receivers.add(int(parts[1]))
                except ValueError:
                    continue
    return receivers


def _parse_flow_start_times(flow_path):
    starts = []
    with open(flow_path, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 6:
                try:
                    starts.append(float(parts[5]))
                except ValueError:
                    continue
    return sorted(set(starts))


def parse_schedules(config_file):
    """Parse config file to extract RX_PULL_RATE_SCHEDULE."""
    schedules = {}
    if not config_file or not os.path.exists(config_file):
        return schedules
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if 'RX_PULL_RATE_SCHEDULE' in line:
                parts = line.split()
                if len(parts) < 2 or parts[0] != 'RX_PULL_RATE_SCHEDULE':
                    continue
                
                # New format: node:time,rate;time,rate...
                if ':' in parts[1]:
                    try:
                        node_id_str, sched_str = parts[1].split(':', 1)
                        node_id = int(node_id_str)
                        sched = []
                        for entry in sched_str.split(';'):
                            if ',' in entry:
                                t_str, r_str = entry.split(',', 1)
                                t = float(t_str)
                                if t > 1000000: t /= 1e9
                                sched.append((t, float(r_str)))
                        schedules[node_id] = sched
                    except: pass
                # Old format: node count time1 rate1 ...
                elif len(parts) >= 4:
                    try:
                        node_id = int(parts[1])
                        count = int(parts[2])
                        sched = []
                        idx = 3
                        for _ in range(count):
                            if idx + 1 < len(parts):
                                t = float(parts[idx])
                                if t > 1000000: t /= 1e9
                                sched.append((t, float(parts[idx+1])))
                                idx += 2
                        schedules[node_id] = sched
                    except: pass
    return schedules

def _draw_lines(plt, schedules):
    """Utility to draw vertical lines and labels for schedules."""
    for node_id, schedule in schedules.items():
        for time, rate in schedule:
            plt.axvline(x=time, color='gray', linestyle=':', alpha=0.6, linewidth=1.5)
            plt.text(time, plt.gca().get_ylim()[1], f' t={time}s\nRate={rate}', 
                    rotation=90, verticalalignment='top', fontsize=8, alpha=0.7)

import struct
import os
from trace_parsers import parse_rxbuf_series

def plot_rx_buffer(filename, output_file=None, config_file=None):
    data = parse_rxbuf_series(filename)
    if filename.endswith('.tr') and data:
        print(f"Successfully parsed binary RX buffer file: {filename}")

    if not data:
        print("No data found in file")
        return

    # Get max buffer limits and which nodes are actual receivers.
    max_buffer_size = 8 * 1024 * 1024
    max_buffer_per_queue = 1048576
    receiver_nodes = set()
    schedules = {}
    exp_name = None
    flow_start_times = []
    if config_file:
        parsed = parse_config(config_file)
        if parsed["rx_buffer_size"] is not None:
            max_buffer_size = parsed["rx_buffer_size"]
        if parsed["rx_buffer_per_queue"] is not None:
            max_buffer_per_queue = parsed["rx_buffer_per_queue"]
        receiver_nodes = parsed["receiver_nodes"]
        exp_name = parsed.get("exp_name")
        flow_start_times = parsed.get("flow_start_times", [])
        schedules = parse_schedules(config_file)

    if receiver_nodes:
        data = defaultdict(lambda: {"t": [], "bytes": []}, {
            key: value for key, value in data.items() if key[0] in receiver_nodes
        })

    if not data:
        print("No RX buffer samples found for receiver nodes")
        return

    # Determine best unit for Y-axis after receiver filtering.
    max_data_val = 0
    for series in data.values():
        if series["bytes"]:
            max_data_val = max(max_data_val, max(series["bytes"]))

    # Determine scale factor and unit
    # Use the larger of data max or limit to guide scaling, but prefer data readability
    # If usage is tiny (e.g. 6KB) vs Limit (1MB), we might want to scale for Data
    # but still show the limit line context.
    
    reference_val = max(max_data_val, max_buffer_size / 10) # Heuristic
    
    if reference_val >= 1024 * 1024:
        scale = 1024 * 1024
        unit = "MB"
    elif reference_val >= 1024:
        scale = 1024
        unit = "KB"
    else:
        scale = 1
        unit = "Bytes"

    plt.figure(figsize=(12, 6))
    
    # Track max values for annotations
    annotated_series = []
    
    for (node, ifidx), series in sorted(data.items()):
        label = f"node {node} if {ifidx}"
        # Scale data
        scaled_bytes = [b / scale for b in series["bytes"]]
        line, = plt.plot(series["t"], scaled_bytes, label=label, linewidth=1.5)
        
        # Find and annotate maximum value
        if series["bytes"]:
            max_bytes = max(series["bytes"])
            if max_bytes > 0:  # Only annotate if there's actual data
                max_idx = series["bytes"].index(max_bytes)
                max_time = series["t"][max_idx]
                max_val_scaled = max_bytes / scale
                
                plt.annotate(f'{max_val_scaled:.2f} {unit}', 
                            xy=(max_time, max_val_scaled),
                            xytext=(10, 10), textcoords='offset points',
                            fontsize=8, color=line.get_color(),
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                                    edgecolor=line.get_color(), alpha=0.8),
                            arrowprops=dict(arrowstyle='->', color=line.get_color(), lw=1))
                annotated_series.append((node, ifidx, max_bytes, max_time))

    # Show only configured per-queue limit as requested.
    scaled_queue_limit = max_buffer_per_queue / scale
    plt.axhline(y=scaled_queue_limit, color='red', linestyle='--', linewidth=2.0,
                label=f'Per-queue limit ({scaled_queue_limit:.2f} {unit})', alpha=0.9, zorder=10)

    # Add vertical lines for pulling rate schedule
    colors = ['green', 'purple', 'orange', 'brown'] # Cycle colors for different nodes if needed
    color_idx = 0
    for node_id, schedule in schedules.items():
        # Check if this node is in the plotted data (ignoring interface index)
        if any(d_node == node_id for d_node, _ in data.keys()):
            for time, rate in schedule:
                plt.axvline(x=time, color='gray', linestyle=':', alpha=0.6)
                # Annotate the rate
                plt.text(time, plt.ylim()[1] * 0.95, f' t={time}s\nRate={rate}', rotation=90, verticalalignment='top', fontsize=8, color='black', fontweight='bold')

    # Case-specific markers for elephants_rx_buffer experiments only.
    if exp_name in {"elephants_rx_buffer_HPPC", "elephants_rx_buffer_HPPC_Plus"} and flow_start_times:
        ymax = plt.ylim()[1]
        for idx, t in enumerate(flow_start_times):
            plt.axvline(x=t, color='purple', linestyle='--', alpha=0.7, linewidth=1.2)
            if idx % 2 == 0:
                plt.text(t, ymax * 0.90, f'flow start {t:.1f}s', rotation=90,
                         verticalalignment='top', fontsize=8, color='purple')


    plt.xlabel("Time (s)")
    plt.ylabel(f"RX buffer ({unit})")
    receiver_text = ""
    if receiver_nodes:
        receiver_text = f" - Receiver node(s): {', '.join(str(n) for n in sorted(receiver_nodes))}"
    plt.title(f"NIC RX Buffer Occupancy Over Time{receiver_text} (Max: {max_data_val/scale:.2f} {unit})")
    # Clamp axis to 1.05x per-queue limit for visibility and consistent comparison.
    ymax = scaled_queue_limit * 1.05 if scaled_queue_limit > 0 else 1
    plt.ylim(0, ymax)
    plt.grid(True, alpha=0.3)
    plt.legend(loc='best', framealpha=0.9)
    plt.tight_layout()

    if output_file is None:
        output_file = filename.replace(".txt", ".png")
        if output_file == filename:
            output_file = filename + ".png"
    plt.savefig(output_file, dpi=150)
    print(f"RX buffer plot saved to: {output_file}")
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot NIC RX buffer occupancy over time")
    parser.add_argument("input", nargs="?", default="results/data/rxbuf_two_senders_heavy.txt",
                        help="Path to RX buffer trace file")
    parser.add_argument("--out", default=None, help="Output PNG path")
    parser.add_argument("--config", default="simulation/mix/configs/config_two_senders_per_node.txt",
                        help="Path to config file (to read RX_BUFFER_PER_QUEUE)")
    args = parser.parse_args()

    plot_rx_buffer(args.input, args.out, args.config)
