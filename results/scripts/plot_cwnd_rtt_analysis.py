#!/usr/bin/env python3
"""
Generate comprehensive CWND/Rate analysis dashboard.
Dynamically adapts to any simulation data - robust for different topologies/flows.

Input:
  - cwnd_data_file: CWND trace file (time_ns, src, dst, sport, dport, rate_bps, win_bytes)
  - output_file: Output PNG path

Features:
    - Plots all flows in Window over Time panel
    - Sender rate over time panel
    - Per-flow throughput summary in console output
"""
import sys
import argparse
import statistics
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]


def _subsample_series(xs, ys, max_points=400000):
    if len(xs) <= max_points:
        return xs, ys
    step = max(1, len(xs) // max_points)
    indices = list(range(0, len(xs), step))
    if indices[-1] != (len(xs) - 1):
        indices.append(len(xs) - 1)
    if ys:
        max_idx = max(range(len(ys)), key=lambda i: ys[i])
        min_idx = min(range(len(ys)), key=lambda i: ys[i])
        indices.extend([max_idx, min_idx])
    indices = sorted(set(indices))
    xs_sub = [xs[i] for i in indices]
    ys_sub = [ys[i] for i in indices]
    if xs_sub and xs_sub[-1] != xs[-1]:
        xs_sub.append(xs[-1])
        ys_sub.append(ys[-1])
    return xs_sub, ys_sub


def _extract_steady_state_period(data):
    """Find the steady-state period where transmission is active."""
    times = [t for t, _, _, _, _ in data]
    if not times:
        return None, None
    
    # Steady state is roughly in the middle 50% of active transmission
    t_min, t_max = min(times), max(times)
    duration = t_max - t_min
    steady_start = t_min + duration * 0.2  # Skip first 20%
    steady_end = t_min + duration * 0.9    # Use up to 90%
    
    return steady_start, steady_end


import struct
import os

def _cap_flow_points(flow_data, max_points_per_flow):
    if max_points_per_flow <= 0:
        return
    if len(flow_data["t"]) <= max_points_per_flow:
        return
    # Keep memory bounded: when a flow grows too large, downsample it in-place.
    if len(flow_data["t"]) >= (2 * max_points_per_flow):
        flow_data["t"] = flow_data["t"][::2]
        flow_data["win"] = flow_data["win"][::2]
        flow_data["rate"] = flow_data["rate"][::2]


def _parse_cwnd_file(cwnd_file, read_stride=1, max_points_per_flow=0, max_flows=0):
    """Parse CWND file and return flows with their data."""
    flows = defaultdict(lambda: {"t": [], "win": [], "rate": []})
    read_stride = max(1, int(read_stride))
    max_points_per_flow = max(0, int(max_points_per_flow))
    max_flows = max(0, int(max_flows))
    dropped_new_flows = 0
    
    # Try reading as binary first
    is_binary = cwnd_file.endswith('.tr')
    if not is_binary:
        try:
            with open(cwnd_file, 'rb') as f:
                header = f.read(8)
                if len(header) == 8:
                    # Heuristic: if first 8 bytes (time) is non-zero and small, or contains zeros
                    if any(b == 0 for b in header):
                        is_binary = True
        except:
            pass

    if is_binary:
        try:
            # CwndTrace native layout (little-endian on this Linux build):
            # uint64 time; uint32 sip,dip,sport,dport; uint64 rate,win,lastRtt; uint32 lastAckSeq; pad4.
            dtype = np.dtype([
                ("time", "<u8"),
                ("sip", "<u4"),
                ("dip", "<u4"),
                ("sport", "<u4"),
                ("dport", "<u4"),
                ("rate", "<u8"),
                ("win", "<u8"),
                ("lastRtt", "<u8"),
                ("lastAckSeq", "<u4"),
                ("_pad", "<u4"),
            ])
            with open(cwnd_file, 'rb') as f:
                raw = f.read()
            if len(raw) < dtype.itemsize:
                return flows

            arr = np.frombuffer(raw, dtype=dtype)
            if read_stride > 1:
                arr = arr[::read_stride]

            if arr.size == 0:
                return flows

            key_a = (arr["sip"].astype(np.uint64) << 32) | arr["dip"].astype(np.uint64)
            key_b = (arr["sport"].astype(np.uint64) << 32) | arr["dport"].astype(np.uint64)
            sort_idx = np.lexsort((key_b, key_a))
            arr = arr[sort_idx]
            key_a = key_a[sort_idx]
            key_b = key_b[sort_idx]
            boundaries = np.where((np.diff(key_a) != 0) | (np.diff(key_b) != 0))[0] + 1
            flow_chunks = np.split(arr, boundaries)

            if max_flows:
                kept_chunks = flow_chunks[:max_flows]
                for chunk in flow_chunks[max_flows:]:
                    dropped_new_flows += len(chunk)
                flow_chunks = kept_chunks

            for chunk in flow_chunks:
                src = int(chunk["sip"][0])
                dst = int(chunk["dip"][0])
                sport = int(chunk["sport"][0])
                dport = int(chunk["dport"][0])
                key = (src, dst, sport, dport)

                t_vals = (chunk["time"] / 1e9).tolist()
                win_vals = chunk["win"].astype(np.float64).tolist()
                rate_vals = chunk["rate"].astype(np.float64).tolist()

                if max_points_per_flow and len(t_vals) > max_points_per_flow:
                    step = max(1, len(t_vals) // max_points_per_flow)
                    idx = list(range(0, len(t_vals), step))
                    if idx[-1] != (len(t_vals) - 1):
                        idx.append(len(t_vals) - 1)
                    win_np = np.asarray(win_vals)
                    idx.extend([int(np.argmax(win_np)), int(np.argmin(win_np))])
                    idx = sorted(set(idx))
                    t_vals = [t_vals[i] for i in idx]
                    win_vals = [win_vals[i] for i in idx]
                    rate_vals = [rate_vals[i] for i in idx]

                flows[key]["t"] = t_vals
                flows[key]["win"] = win_vals
                flows[key]["rate"] = rate_vals

            if flows:
                print(f"Successfully parsed binary CWND file: {cwnd_file}")
                if dropped_new_flows:
                    print(f"Dropped {dropped_new_flows} records from flows beyond max_flows={max_flows}")
                return flows
        except Exception as e:
            print(f"Error parsing binary CWND file {cwnd_file}: {e}")
            is_binary = False

    if not is_binary:
        with open(cwnd_file, 'r') as f:
            rec_idx = 0
            for line in f:
                rec_idx += 1
                if (rec_idx % read_stride) != 0:
                    continue
                parts = line.strip().split()
                if len(parts) < 7:
                    continue
                try:
                    t_ns = int(parts[0])
                    src = int(parts[1])
                    dst = int(parts[2])
                    sport = int(parts[3])
                    dport = int(parts[4])
                    rate = int(parts[5])
                    win = int(parts[6])
                    
                    key = (src, dst, sport, dport)
                    if key not in flows and max_flows and len(flows) >= max_flows:
                        dropped_new_flows += 1
                        continue
                    flows[key]["t"].append(t_ns / 1e9)
                    flows[key]["win"].append(win)
                    flows[key]["rate"].append(rate)
                    _cap_flow_points(flows[key], max_points_per_flow)
                except (ValueError, IndexError):
                    continue

    if dropped_new_flows:
        print(f"Dropped {dropped_new_flows} records from flows beyond max_flows={max_flows}")
    
    return flows


def _parse_flow_file(flow_file_path):
    flow_specs = []
    path = Path(flow_file_path)
    if not path.exists():
        return flow_specs

    with open(path, 'r') as f:
        lines = [line.strip() for line in f if line.strip() and not line.lstrip().startswith('#')]

    if not lines:
        return flow_specs

    start_idx = 1 if lines[0].isdigit() else 0
    for line in lines[start_idx:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            flow_specs.append({
                "src": int(parts[0]),
                "dst": int(parts[1]),
                "dport": int(parts[3]),
                "start_time": float(parts[5]),
            })
        except ValueError:
            continue
    return flow_specs


def _resolve_config_reference(config_path, referenced_path):
    if not config_path or not referenced_path:
        return None

    raw_path = Path(referenced_path)
    if raw_path.is_absolute() and raw_path.exists():
        return raw_path

    config_parent = Path(config_path).resolve().parent
    candidates = [
        config_parent / raw_path,
        REPO_ROOT / raw_path,
    ]

    raw_parts = raw_path.parts
    while raw_parts and raw_parts[0] == "..":
        raw_parts = raw_parts[1:]
    if raw_parts:
        candidates.append(REPO_ROOT.joinpath(*raw_parts))

    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved
    return None


def _load_expected_flows(config_path):
    cfg = _parse_config(config_path)
    flow_file = cfg.get("FLOW_FILE")
    if not flow_file:
        return []
    flow_path = _resolve_config_reference(config_path, flow_file)
    if flow_path is None:
        return []
    return _parse_flow_file(flow_path)


def _group_flows_by_expected_apps(flows, expected_flows):
    if not expected_flows:
        return flows

    grouped = {}
    for spec in expected_flows:
        key = (spec["src"], spec["dst"], spec["dport"])
        grouped[key] = {
            "t": [],
            "win": [],
            "rate": [],
            "label": f"Flow {spec['src']}→{spec['dst']} (dport {spec['dport']})",
            "start_time": spec["start_time"],
        }

    for (src, dst, _sport, dport), data in flows.items():
        app_key = (src, dst, dport)
        if app_key not in grouped:
            continue
        grouped[app_key]["t"].extend(data["t"])
        grouped[app_key]["win"].extend(data["win"])
        grouped[app_key]["rate"].extend(data["rate"])

    compact = {}
    for spec in expected_flows:
        key = (spec["src"], spec["dst"], spec["dport"])
        data = grouped[key]
        if not data["t"]:
            continue
        merged = sorted(zip(data["t"], data["win"], data["rate"]), key=lambda item: item[0])
        compact[key] = {
            "t": [item[0] for item in merged],
            "win": [item[1] for item in merged],
            "rate": [item[2] for item in merged],
            "label": data["label"],
            "start_time": data["start_time"],
        }
    return compact


def _aggregate_throughput_by_app(throughput_map):
    aggregated = {}
    for (src, dst, _sport, dport), throughput in throughput_map.items():
        aggregated[(src, dst, dport)] = throughput
    return aggregated


def _flow_label(flow_key, data):
    if data.get("label"):
        return data["label"]
    if len(flow_key) == 4:
        src, dst, sport, dport = flow_key
        return f"Flow {src}→{dst} ({sport}→{dport})"
    src, dst, dport = flow_key
    return f"Flow {src}→{dst} (dport {dport})"


def _flow_src(flow_key):
    return flow_key[0]


def _get_effective_sampling_limits(expected_flows, read_stride, max_points_per_flow, max_flows, max_flows_plot):
    if not expected_flows:
        return read_stride, max_points_per_flow, max_flows, max_flows_plot

    expected_count = len(expected_flows)
    if expected_count <= 4:
        effective_stride = 1 if read_stride <= 4 else read_stride
        effective_points = max(max_points_per_flow, 1000000)
        effective_max_flows = expected_count if max_flows <= 0 else min(max_flows, expected_count)
        effective_max_flows_plot = min(max(max_flows_plot, expected_count), expected_count)
        return effective_stride, effective_points, effective_max_flows, effective_max_flows_plot

    return read_stride, max_points_per_flow, max_flows, max_flows_plot


def _flow_start_time(flow_key, data, default_start_time):
    return float(data.get("start_time", default_start_time))


def _filter_series_from_time(times, values, start_time):
    filtered = [(t, value) for t, value in zip(times, values) if t >= start_time]
    if not filtered:
        return [], []
    return [item[0] for item in filtered], [item[1] for item in filtered]


def _parse_fct_file(fct_file_path):
    """Parse FCT file to get actual throughput per flow."""
    throughput_map = {}

    is_binary = str(fct_file_path).endswith('.tr')
    if is_binary:
        try:
            import struct
            # FctTrace: sip(I), dip(I), sport(I), dport(I), size(Q), startTime(Q), fct(Q), standaloneFct(Q)
            fmt = "IIIIQQQQ"
            sz = struct.calcsize(fmt)
            with open(fct_file_path, 'rb') as f:
                while True:
                    data = f.read(sz)
                    if not data or len(data) < sz:
                        break
                    sip, dip, sport, dport, size_bytes, start_ns, fct_ns, _ = struct.unpack(fmt, data)
                    duration_s = fct_ns / 1e9
                    if duration_s > 0:
                        throughput_bps = (size_bytes * 8) / duration_s
                        # CWND traces store node ids for src/dst in this codebase.
                        throughput_map[(sip, dip, sport, dport)] = throughput_bps
            return throughput_map
        except Exception:
            # Fall through to text parser for robustness.
            pass

    try:
        with open(fct_file_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 8:
                    # Format: src_ip dst_ip sport dport size start_time complete_time base_rtt
                    sport = int(parts[2])
                    dport = int(parts[3])
                    size_bytes = int(parts[4])
                    start_ns = int(parts[5])
                    complete_ns = int(parts[6])
                    
                    # Extract src/dst from IP (0b000X01 format)
                    src_ip = parts[0]
                    dst_ip = parts[1]
                    src = int(src_ip[5], 16) if len(src_ip) >= 6 else 0
                    dst = int(dst_ip[5], 16) if len(dst_ip) >= 6 else 0
                    
                    duration_s = (complete_ns - start_ns) / 1e9
                    if duration_s > 0:
                        throughput_bps = (size_bytes * 8) / duration_s
                        throughput_map[(src, dst, sport, dport)] = throughput_bps
    except FileNotFoundError:
        pass
    return throughput_map


def _get_steady_state_stats(flows, fct_throughput_map=None):
    """Calculate steady-state CWND and rate for each flow."""
    stats = {}
    
    for flow_key, data in flows.items():
        times = data["t"]
        wins = data["win"]
        rates = data["rate"]
        
        if not times:
            continue
        
        # Find steady state (middle 70% of transmission)
        t_min, t_max = min(times), max(times)
        duration = t_max - t_min
        steady_start = t_min + duration * 0.15
        steady_end = t_max - duration * 0.1
        
        # Extract steady-state samples
        steady_wins = [w for t, w in zip(times, wins) if steady_start <= t <= steady_end and w > 0]
        steady_rates = [r for t, r in zip(times, rates) if steady_start <= t <= steady_end and r > 0]
        
        if steady_wins and steady_rates:
            stats[flow_key] = {
                "cwnd_avg": statistics.mean(steady_wins),
                "rate_avg": statistics.mean(steady_rates),  # HPCC target rate
                "fct": t_max  # Flow completion time
            }
            
            # Add actual throughput if available from FCT
            if fct_throughput_map and flow_key in fct_throughput_map:
                stats[flow_key]["actual_throughput"] = fct_throughput_map[flow_key]
    
    return stats


def _parse_rate_to_bps(rate_str):
    if rate_str is None:
        return None
    s = str(rate_str).strip()
    try:
        return float(s)
    except ValueError:
        pass
    s = s.lower()
    if s.endswith("gbps"):
        return float(s[:-4]) * 1e9
    if s.endswith("mbps"):
        return float(s[:-4]) * 1e6
    if s.endswith("kbps"):
        return float(s[:-4]) * 1e3
    if s.endswith("bps"):
        return float(s[:-3])
    return None


def _parse_config(config_path):
    cfg = {}
    if not config_path or not Path(config_path).exists():
        return cfg
    with open(config_path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("{") or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            key = parts[0]
            value = parts[1]
            cfg[key] = value
    return cfg


def _parse_topology_min_rate(topo_path):
    if not topo_path or not Path(topo_path).exists():
        return None
    rates = []
    with open(topo_path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 5:
                rate_bps = _parse_rate_to_bps(parts[2])
                if rate_bps:
                    rates.append(rate_bps)
    return min(rates) if rates else None


def _parse_delay_to_ns(delay_str):
    if delay_str is None:
        return None
    s = str(delay_str).strip().lower()
    try:
        return int(float(s))
    except ValueError:
        pass
    if s.endswith("ns"):
        return int(float(s[:-2]))
    if s.endswith("us"):
        return int(float(s[:-2]) * 1e3)
    if s.endswith("ms"):
        return int(float(s[:-2]) * 1e6)
    if s.endswith("s"):
        return int(float(s[:-1]) * 1e9)
    return None


def _parse_topology_graph(topo_path):
    topo = {
        "node_types": {},
        "adjacency": defaultdict(list),
    }
    if not topo_path or not Path(topo_path).exists():
        return topo

    with open(topo_path, "r") as f:
        lines = [line.strip() for line in f if line.strip() and not line.lstrip().startswith("#")]

    if len(lines) < 2:
        return topo

    header = lines[0].split()
    if len(header) < 3:
        return topo
    node_count = int(header[0])
    switch_count = int(header[1])
    switch_ids = {int(value) for value in lines[1].split()[:switch_count]}
    for node_id in range(node_count):
        topo["node_types"][node_id] = 1 if node_id in switch_ids else 0

    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        if not (parts[0].isdigit() and parts[1].isdigit()):
            continue
        src = int(parts[0])
        dst = int(parts[1])
        bw = _parse_rate_to_bps(parts[2])
        delay_ns = _parse_delay_to_ns(parts[3])
        if bw is None or delay_ns is None:
            continue
        topo["adjacency"][src].append({"next": dst, "bw": int(bw), "delay_ns": int(delay_ns)})
        topo["adjacency"][dst].append({"next": src, "bw": int(bw), "delay_ns": int(delay_ns)})

    return topo


def _compute_pair_path_metrics(src, dst, topo, packet_payload_size):
    node_types = topo.get("node_types", {})
    adjacency = topo.get("adjacency", {})
    if src not in node_types or dst not in node_types:
        return None

    queue = [src]
    distance = {src: 0}
    delay_ns = {src: 0}
    tx_delay_ns = {src: 0}
    bw_bps = {src: (1 << 62)}

    for current in queue:
        current_distance = distance[current]
        for edge in adjacency.get(current, []):
            nxt = edge["next"]
            if nxt in distance:
                continue
            distance[nxt] = current_distance + 1
            delay_ns[nxt] = delay_ns[current] + edge["delay_ns"]
            tx_delay_ns[nxt] = tx_delay_ns[current] + int(packet_payload_size * 8 * 1e9 / edge["bw"])
            bw_bps[nxt] = min(bw_bps[current], edge["bw"])
            if node_types.get(nxt) == 1:
                queue.append(nxt)

    if dst not in delay_ns or dst not in bw_bps:
        return None

    rtt_ns = delay_ns[dst] * 2 + tx_delay_ns[dst]
    bottleneck_bw_bps = bw_bps[dst]
    bdp_bytes = int(rtt_ns * bottleneck_bw_bps / 1e9 / 8)
    return {
        "rtt_ns": rtt_ns,
        "bottleneck_bw_bps": bottleneck_bw_bps,
        "bdp_bytes": bdp_bytes,
    }


def _compute_flow_path_metrics(expected_flows, topo_path, config_path):
    if not expected_flows:
        return {}
    cfg = _parse_config(config_path)
    packet_payload_size = int(cfg.get("PACKET_PAYLOAD_SIZE", 1000))
    topo = _parse_topology_graph(topo_path)
    metrics_by_flow = {}
    for spec in expected_flows:
        key = (spec["src"], spec["dst"], spec["dport"])
        metrics = _compute_pair_path_metrics(spec["src"], spec["dst"], topo, packet_payload_size)
        if metrics is not None:
            metrics_by_flow[key] = metrics
    return metrics_by_flow


def _compute_host_delay_us(pkt_size_bytes, line_rate_bps, rx_pull_rate):
    if not pkt_size_bytes or not line_rate_bps or rx_pull_rate is None:
        return 0.0
    if rx_pull_rate >= 1.0:
        return 0.0
    base_time = (pkt_size_bytes * 8.0) / line_rate_bps
    pull_time = (pkt_size_bytes * 8.0) / (line_rate_bps * rx_pull_rate)
    extra = pull_time - base_time
    return max(extra * 1e6, 0.0)



def _parse_schedules(config_file):
    """Parse config file to extract RX_PULL_RATE_SCHEDULE."""
    schedules = {}
    if not config_file or not Path(config_file).exists():
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

# helper for plotting lines
def _draw_lines(ax, schedules):
    for node_id, schedule in schedules.items():
            for time, rate in schedule:
                ax.axvline(x=time, color='gray', linestyle=':', alpha=0.8, linewidth=1.5)
                # Using transform=ax.transAxes pins the text to the top of the plot independent of RTT spikes
                ax.text(time, 0.98, f' t={time}s\nRate={rate}', rotation=90, 
                        transform=ax.get_xaxis_transform(),
                        verticalalignment='top', fontsize=8, color='black', alpha=0.7)


def plot_cwnd_rtt_analysis(
    cwnd_file,
    output_file,
    config_path=None,
    topo_path=None,
    rtt_ymax=None,
    read_stride=1,
    max_points_per_flow=0,
    max_flows=0,
    max_flows_plot=12,
    plot_start_time=0.0,
):
    """Generate comprehensive CWND/Rate analysis dashboard."""
    expected_flows = _load_expected_flows(config_path) if config_path else []
    read_stride, max_points_per_flow, max_flows, max_flows_plot = _get_effective_sampling_limits(
        expected_flows,
        read_stride,
        max_points_per_flow,
        max_flows,
        max_flows_plot,
    )

    # Parse data
    flows = _parse_cwnd_file(
        cwnd_file,
        read_stride=read_stride,
        max_points_per_flow=max_points_per_flow,
        max_flows=max_flows,
    )
    if not flows:
        print("ERROR: No flows found in CWND file")
        return
    
    # Try to load FCT data for actual throughput
    fct_file = cwnd_file.replace('cwnd_', 'fct_')
    fct_throughput_map = _parse_fct_file(fct_file)
    if expected_flows:
        flows = _group_flows_by_expected_apps(flows, expected_flows)
        fct_throughput_map = _aggregate_throughput_by_app(fct_throughput_map)
    if not flows:
        print("ERROR: No expected flows found in CWND file")
        return
    
    # Get statistics
    stats = _get_steady_state_stats(flows, fct_throughput_map)
    # Parse schedules
    schedules = _parse_schedules(config_path) if config_path else {}

    # Prepare data
    max_win = max([max(data["win"]) for data in flows.values() if data["win"]])
    max_flows_plot = max(1, int(max_flows_plot))
    if expected_flows:
        plotted_flow_items = []
        for spec in expected_flows:
            key = (spec["src"], spec["dst"], spec["dport"])
            if key in flows:
                plotted_flow_items.append((key, flows[key]))
    else:
        flow_items = sorted(flows.items(), key=lambda kv: len(kv[1]["t"]), reverse=True)
        plotted_flow_items = flow_items[:max_flows_plot]

    if not plotted_flow_items:
        print("ERROR: No plottable flows found in CWND file")
        return

    plot_start_time = float(plot_start_time)
    
    # Determine units
    if max_win >= 1e6:
        win_unit, win_scale = "KB", 1024
    else:
        win_unit, win_scale = "B", 1
    
    # Get line rate from topology
    line_rate_bps = _parse_topology_min_rate(topo_path) if topo_path else 1e9  # Default 1 Gbps
    flow_path_metrics = _compute_flow_path_metrics(expected_flows, topo_path, config_path) if config_path and topo_path else {}
    bdp_by_flow = {flow_key: metrics["bdp_bytes"] for flow_key, metrics in flow_path_metrics.items()}
    
    # Create figure with two plots
    fig = plt.figure(figsize=(12, 7.5))
    
    # Add spacing at top for title
    fig.suptitle('CWND and Sending Rate Analysis', 
                 fontsize=16, fontweight='bold', y=0.96)
    
    # CWND vs Time (all flows)
    ax1 = plt.subplot(211)
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    linestyles = ['-', '--', '-.', ':', '-', '--']
    
    for idx, (flow_key, data) in enumerate(plotted_flow_items):
        label = _flow_label(flow_key, data)
        y = [w / win_scale for w in data["win"]]
        flow_start_time = _flow_start_time(flow_key, data, plot_start_time)
        t_plot, y_plot = _filter_series_from_time(data["t"], y, flow_start_time)
        if not t_plot:
            continue
        line_style = linestyles[idx % len(linestyles)]
        color = colors[idx % len(colors)]

        t_sub, y_sub = _subsample_series(t_plot, y_plot)
        ax1.plot(t_sub, y_sub, label=label, linewidth=2,
                linestyle=line_style, color=color)

    plotted_bdp_labels = set()
    for idx, (flow_key, data) in enumerate(plotted_flow_items):
        bdp_bytes = bdp_by_flow.get(flow_key)
        if bdp_bytes is None:
            continue
        bdp_value = bdp_bytes / win_scale
        label = _flow_label(flow_key, data)
        bdp_label = f"BDP {label}"
        if len(bdp_by_flow) == 1:
            bdp_label = f"BDP ({bdp_value:.1f} {win_unit})"
        elif bdp_label in plotted_bdp_labels:
            bdp_label = None
        plotted_bdp_labels.add(f"BDP {_flow_label(flow_key, data)}")
        ax1.axhline(
            y=bdp_value,
            color=colors[idx % len(colors)],
            linestyle=':',
            alpha=0.8,
            linewidth=1.8,
            label=bdp_label,
        )
    
    # Mark FCT for primary flow
    if flows:
        first_flow = list(flows.values())[0]
        fct = max(first_flow["t"])
        ax1.axvline(x=fct, color='green', linestyle='--', alpha=0.6, linewidth=1.5, label='FCT')
    
    ax1.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax1.set_ylabel(f'CWND ({win_unit})', fontsize=11, fontweight='bold')
    ax1.set_title('Window Size Over Time', fontsize=12, fontweight='bold', pad=10)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best', fontsize=9)
    ax1.set_ylim([0, max_win / win_scale * 1.25])
    ax1.set_xlim(left=plot_start_time)
    if schedules: _draw_lines(ax1, schedules)
    
    # Rate vs Time (senders only - nodes 0 and 1)
    ax2 = plt.subplot(212)
    max_rate_gbps = 0.0
    
    for idx, (flow_key, data) in enumerate(plotted_flow_items):
        src = _flow_src(flow_key)
        if src not in [0, 1]:
            continue

        label = data.get("label", f"Sender {src}")
        y = [r / 1e9 for r in data["rate"]]
        flow_start_time = _flow_start_time(flow_key, data, plot_start_time)
        t_plot, y_plot = _filter_series_from_time(data["t"], y, flow_start_time)
        if not t_plot:
            continue
        max_rate_gbps = max(max_rate_gbps, max(y_plot))
        line_style = linestyles[idx % len(linestyles)]
        color = colors[idx % len(colors)]

        t_sub, y_sub = _subsample_series(t_plot, y_plot)
        ax2.plot(t_sub, y_sub, label=label, linewidth=2,
                linestyle=line_style, color=color)

    plotted_line_rate_labels = set()
    for idx, (flow_key, data) in enumerate(plotted_flow_items):
        metrics = flow_path_metrics.get(flow_key)
        if not metrics:
            continue
        line_rate_gbps = metrics["bottleneck_bw_bps"] / 1e9
        label = _flow_label(flow_key, data)
        rate_label = f"Line Rate {label}"
        if len(flow_path_metrics) == 1:
            rate_label = f"Line Rate ({line_rate_gbps:.1f} Gbps)"
        elif rate_label in plotted_line_rate_labels:
            rate_label = None
        plotted_line_rate_labels.add(f"Line Rate {_flow_label(flow_key, data)}")
        ax2.axhline(
            y=line_rate_gbps,
            color=colors[idx % len(colors)],
            linestyle=':',
            alpha=0.8,
            linewidth=1.8,
            label=rate_label,
        )
    
    ax2.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Sending Rate (Gbps)', fontsize=11, fontweight='bold')
    ax2.set_title('Sender Rates Over Time', fontsize=12, fontweight='bold', pad=10)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', fontsize=9)
    ax2.set_xlim(left=plot_start_time)
    
    if line_rate_bps:
        topology_line_rate_gbps = line_rate_bps / 1e9
        plotted_line_rate_gbps = [metrics["bottleneck_bw_bps"] / 1e9 for metrics in flow_path_metrics.values()]
        reference_rate_gbps = max([topology_line_rate_gbps] + plotted_line_rate_gbps) if plotted_line_rate_gbps else topology_line_rate_gbps
        ax2.set_ylim([0, max(reference_rate_gbps * 1.1, max_rate_gbps * 1.1 if max_rate_gbps else 0.0)])
    elif max_rate_gbps:
        ax2.set_ylim([0, max_rate_gbps * 1.1])
    if schedules: _draw_lines(ax2, schedules)
    
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✓ Analysis dashboard saved to: {output_file}")
    
    if config_path:
        print(f"  Config: {config_path}")
    if topo_path:
        print(f"  Topology: {topo_path}")
    print(f"  Flows retained: {len(flows)} (plotted: {len(plotted_flow_items)})")
    plotted_keys = {flow_key for flow_key, _ in plotted_flow_items}
    for flow_key, stat in sorted(stats.items()):
        if flow_key not in plotted_keys:
            continue
        if "actual_throughput" in stat:
            throughput_str = f"{stat['actual_throughput']/1e9:.3f} Gbps (actual)"
        else:
            throughput_str = f"{stat['rate_avg']/1e9:.3f} Gbps (target)"
        print(f"    {_flow_label(flow_key, flows[flow_key])}: {throughput_str}, "
              f"CWND: {stat['cwnd_avg']/1024:.2f} KB")
        if flow_key in bdp_by_flow:
            print(f"      BDP: {bdp_by_flow[flow_key] / 1024:.2f} KB")
    
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate CWND analysis")
    parser.add_argument("cwnd_file", help="Input CWND text file")
    parser.add_argument("output_file", nargs="?", help="Output PNG file")
    parser.add_argument("config_path", nargs="?", help="Configuration file path")
    parser.add_argument("topo_path", nargs="?", help="Topology file path")
    parser.add_argument("--rtt-ymax", type=float, help="Fixed Y-axis limit for RTT plot (us)")
    parser.add_argument("--read-stride", type=int, default=1, help="Read every Nth CWND record to reduce parse/plot time")
    parser.add_argument("--max-points-per-flow", type=int, default=80000, help="Maximum retained points per flow during parsing (0 disables cap)")
    parser.add_argument("--max-flows", type=int, default=200, help="Maximum number of flows to retain during parsing (0 disables cap)")
    parser.add_argument("--max-flows-plot", type=int, default=12, help="Maximum number of highest-activity flows to plot")
    parser.add_argument("--plot-start-time", type=float, default=0.0, help="Start the x-axis at this time in seconds")
    
    args = parser.parse_args()
    
    cwnd_file = args.cwnd_file
    output_file = args.output_file if args.output_file else cwnd_file.replace('.txt', '_analysis.png')
    
    plot_cwnd_rtt_analysis(
        cwnd_file,
        output_file,
        config_path=args.config_path,
        topo_path=args.topo_path,
        rtt_ymax=args.rtt_ymax,
        read_stride=args.read_stride,
        max_points_per_flow=args.max_points_per_flow,
        max_flows=args.max_flows,
        max_flows_plot=args.max_flows_plot,
        plot_start_time=args.plot_start_time,
    )
