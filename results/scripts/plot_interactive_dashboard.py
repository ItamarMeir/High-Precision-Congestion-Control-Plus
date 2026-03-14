#!/usr/bin/env python3
"""Unified script to generate interactive HTML plots for simulation data using Plotly.js.

Supported plots:
- INT Queue Depth (from queue_depth.csv)
- CWND/Rate/RTT (from cwnd_*.txt)
- RX Buffer (from rxbuf_*.txt)
- Switch Throughput (from binary *.tr)
"""
import argparse
import csv
import json
import os
import struct
import ctypes
from collections import defaultdict
from pathlib import Path

from plot_cwnd_rtt_analysis import (
    _compute_flow_path_metrics,
    _filter_series_from_time,
    _flow_label,
    _flow_start_time,
    _get_effective_sampling_limits,
    _group_flows_by_expected_apps,
    _load_expected_flows,
    _parse_cwnd_file,
    _resolve_config_reference,
    _subsample_series,
)
from plot_switch_throughput import parse_switch_dequeue_bins
from trace_parsers import parse_queue_depth_binned, parse_rxbuf_series

# --- Trace Parsing Logic (Binary Format) ---

class _Data(ctypes.LittleEndianStructure):
    _fields_ = [("sport", ctypes.c_uint16), ("dport", ctypes.c_uint16), ("seq", ctypes.c_uint32),
                ("ts", ctypes.c_uint64), ("pg", ctypes.c_uint16), ("payload", ctypes.c_uint16)]

class _Cnp(ctypes.LittleEndianStructure):
    _fields_ = [("fid", ctypes.c_uint16), ("qIndex", ctypes.c_uint8), ("ecnBits", ctypes.c_uint8), ("qfb_or_seq", ctypes.c_uint32)]

class _Ack(ctypes.LittleEndianStructure):
    _fields_ = [("sport", ctypes.c_uint16), ("dport", ctypes.c_uint16), ("flags", ctypes.c_uint16),
                ("pg", ctypes.c_uint16), ("seq", ctypes.c_uint32), ("ts", ctypes.c_uint64)]

class _Pfc(ctypes.LittleEndianStructure):
    _fields_ = [("time", ctypes.c_uint32), ("qlen", ctypes.c_uint32), ("qIndex", ctypes.c_uint8)]

class _Qp(ctypes.LittleEndianStructure):
    _fields_ = [("sport", ctypes.c_uint16), ("dport", ctypes.c_uint16)]

class _Union(ctypes.Union):
    _fields_ = [("data", _Data), ("cnp", _Cnp), ("ack", _Ack), ("pfc", _Pfc), ("qp", _Qp)]

class Trace(ctypes.LittleEndianStructure):
    _fields_ = [("time", ctypes.c_uint64), ("node", ctypes.c_uint16), ("intf", ctypes.c_uint8),
                ("qidx", ctypes.c_uint8), ("qlen", ctypes.c_uint32), ("sip", ctypes.c_uint32),
                ("dip", ctypes.c_uint32), ("size", ctypes.c_uint16), ("l3Prot", ctypes.c_uint8),
                ("event", ctypes.c_uint8), ("ecn", ctypes.c_uint8), ("nodeType", ctypes.c_uint8), ("u", _Union)]

# --- Helper Functions ---

def _subsample(x, y, max_points=10000):
    """Subsample data to maintain performance while preserving peaks."""
    if len(x) <= max_points:
        return x, y
    step = max(1, len(x) // max_points)
    indices = list(range(0, len(x), step))
    if indices[-1] != len(x) - 1:
        indices.append(len(x) - 1)
    peak_idx = max(range(len(y)), key=lambda idx: y[idx]) if y else None
    if peak_idx is not None and peak_idx not in indices:
        indices.append(peak_idx)
    indices = sorted(set(indices))
    return [x[idx] for idx in indices], [y[idx] for idx in indices]

def generate_plotly_html(traces, layout, output_path, title="Interactive Plot", extra_html="", extra_script=""):
    """Generic Plotly HTML generator."""
    config = {'responsive': True, 'displayModeBar': True, 'scrollZoom': True}
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
        #plot {{ width: 100%; height: 85vh; min-height: 500px; }}
        .help {{ color: #666; font-size: 13px; padding: 10px 0; }}
        .controls {{ margin-bottom: 10px; padding: 10px; background: white; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    {extra_html}
    <div id="plot"></div>
    <div class="help"><b>Controls:</b> Drag to zoom &bull; Double-click to reset &bull; Scroll to zoom &bull; Legend items toggle traces</div>
    <script>
        var plotData = {json.dumps(traces)};
        var plotLayout = {json.dumps(layout)};
        var plotConfig = {json.dumps(config)};
        Plotly.newPlot('plot', plotData, plotLayout, plotConfig).then(function() {{
            {extra_script}
        }});
    </script>
</body>
</html>"""
    with open(output_path, 'w') as f:
        f.write(html)
    print(f"Saved: {output_path}")

def parse_schedules(config_path):
    """Parse RX_PULL_RATE_SCHEDULE from config file."""
    schedules = []
    if not config_path or not os.path.exists(config_path):
        return schedules
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if 'RX_PULL_RATE_SCHEDULE' in line:
                parts = line.split()
                if len(parts) < 2 or parts[0] != 'RX_PULL_RATE_SCHEDULE':
                    continue
                
                # New format: node:time,rate;time,rate...
                if ':' in parts[1]:
                    try:
                        _, sched_str = parts[1].split(':', 1)
                        for entry in sched_str.split(';'):
                            if ',' in entry:
                                t_str, r_str = entry.split(',', 1)
                                t = float(t_str)
                                if t > 1000000: t /= 1e9
                                schedules.append((t, float(r_str)))
                    except: pass
                # Old format: node count time1 rate1 ...
                elif len(parts) >= 4:
                    try:
                        count = int(parts[2])
                        idx = 3
                        for _ in range(count):
                            if idx + 1 < len(parts):
                                t = float(parts[idx])
                                if t > 1000000: t /= 1e9
                                schedules.append((t, float(parts[idx+1])))
                                idx += 2
                    except: pass
    return schedules


def parse_rx_buffer_context(config_path):
    context = {
        'rx_buffer_size': 8 * 1024 * 1024,
        'rx_buffer_per_queue': 1048576,
        'receiver_nodes': set(),
        'flow_file': None,
    }
    if not config_path or not os.path.exists(config_path):
        return context
    with open(config_path, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            if parts[0] == 'RX_BUFFER_SIZE':
                try:
                    context['rx_buffer_size'] = int(parts[1])
                except ValueError:
                    pass
            elif parts[0] == 'RX_BUFFER_PER_QUEUE':
                try:
                    context['rx_buffer_per_queue'] = int(parts[1])
                except ValueError:
                    pass
            elif parts[0] == 'RX_PULL_MODE_NODE' and len(parts) >= 3:
                try:
                    node_id = int(parts[1])
                    pull_mode = int(parts[2])
                    if pull_mode == 1:
                        context['receiver_nodes'].add(node_id)
                except ValueError:
                    pass
            elif parts[0] == 'FLOW_FILE':
                context['flow_file'] = parts[1]

    if not context['receiver_nodes'] and context['flow_file']:
        flow_path = _resolve_config_reference(config_path, context['flow_file'])
        if flow_path and flow_path.exists():
            with open(flow_path, 'r') as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            context['receiver_nodes'].add(int(parts[1]))
                        except ValueError:
                            continue
    return context


def parse_int_hop_metadata(config_path):
    """Return CC mode and configured switch-hop count from a config file."""
    meta = {'cc_mode': None, 'switch_hops': None}
    if not config_path or not os.path.exists(config_path):
        return meta
    with open(config_path, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if not parts:
                continue
            if parts[0] == 'CC_MODE' and len(parts) > 1:
                try:
                    meta['cc_mode'] = int(parts[1])
                except ValueError:
                    pass
            elif parts[0] == 'INT_MULTI' and len(parts) > 1:
                try:
                    meta['switch_hops'] = int(parts[1])
                except ValueError:
                    pass
    return meta

# --- Plot Specific Functions ---

def plot_queue_depth(csv_path, config_path, out_path):
    """Interactive INT Queue Depth with side-by-side CDF."""
    qp_data = defaultdict(lambda: {'t': [], 'q': []})
    bin_s = 0.0001
    hop_meta = parse_int_hop_metadata(config_path)
    allowed_hops = None
    if hop_meta.get('cc_mode') == 11 and hop_meta.get('switch_hops') is not None:
        allowed_hops = set(range(hop_meta['switch_hops']))
    
    max_bins, all_qlens = parse_queue_depth_binned(
        csv_path,
        allowed_hops=allowed_hops,
        bin_s=bin_s,
        collect_all_qlens=True,
        max_sim_time_s=600.0,
    )

    traces = []
    # Plot 1 (Time-series)
    if max_bins:
        sb = sorted(max_bins.keys())
        traces.append({
            'x': [b*bin_s for b in sb], 'y': [max_bins[b] for b in sb], 
            'name': 'Max (All QPs)', 'fill': 'tozeroy', 'line': {'color': 'red'},
            'xaxis': 'x1', 'yaxis': 'y1'
        })
    
    for key, data in qp_data.items():
        xs, qs = _subsample(data['t'], data['q'], 5000)
        traces.append({
            'x': xs, 'y': qs, 'name': key, 
            'visible': 'legendonly', 'xaxis': 'x1', 'yaxis': 'y1'
        })

    # Plot 2 (CDF)
    if all_qlens:
        all_qlens.sort()
        n = len(all_qlens)
        # To keep interactive performance for large traces, we might want to subsample for the CDF
        # or use a fixed number of points. For CDF, 1000 points is usually enough.
        step = max(1, n // 1000)
        xs_cdf = all_qlens[::step]
        ys_cdf = [100.0 * (i * step + 1) / n for i in range(len(xs_cdf))]
        if xs_cdf[-1] != all_qlens[-1]:
            xs_cdf.append(all_qlens[-1])
            ys_cdf.append(100.0)
        traces.append({
            'x': xs_cdf, 'y': ys_cdf, 'name': 'CDF', 
            'line': {'color': 'blue', 'width': 2},
            'xaxis': 'x2', 'yaxis': 'y2'
        })

    schedules = parse_schedules(config_path)
    shapes = [{'type': 'line', 'x0': t, 'x1': t, 'y0': 0, 'y1': 1, 'yref': 'paper', 'line': {'dash': 'dot', 'color': 'gray'}, 'xref': 'x1'} for t, _ in schedules]
    
    layout = {
        'title': 'Switch Queue Depth: Time-Series & CDF',
        'xaxis': {'title': 'Time (s)', 'domain': [0, 0.45], 'rangeslider': {'visible': True}},
        'yaxis': {'title': 'Queue Depth (bytes)'},
        'xaxis2': {'title': 'Queue Depth (bytes)', 'domain': [0.55, 1]},
        'yaxis2': {'title': 'Cumulative Distribution (%)', 'anchor': 'x2', 'range': [0, 105]},
        'shapes': shapes, 'template': 'plotly_white', 'hovermode': 'x unified',
        'legend': {'orientation': 'h', 'y': -0.2}
    }
    generate_plotly_html(traces, layout, out_path, "Switch Queue Depth & CDF")

def plot_cwnd_rtt(cwnd_path, config_path, out_path, rtt_ymax=None):
    """Interactive CWND/Rate dashboard aligned with the static plot behavior."""
    plot_start_time = 0.0
    expected_flows = _load_expected_flows(config_path) if config_path else []
    read_stride, max_points_per_flow, max_flows, max_flows_plot = _get_effective_sampling_limits(
        expected_flows,
        1,
        1000000,
        16,
        4,
    )
    flows = _parse_cwnd_file(
        cwnd_path,
        read_stride=read_stride,
        max_points_per_flow=max_points_per_flow,
        max_flows=max_flows,
    )
    if expected_flows:
        flows = _group_flows_by_expected_apps(flows, expected_flows)
    if not flows:
        print("No CWND samples found")
        return

    if expected_flows:
        plotted_flow_items = []
        for spec in expected_flows:
            key = (spec['src'], spec['dst'], spec['dport'])
            if key in flows:
                plotted_flow_items.append((key, flows[key]))
    else:
        plotted_flow_items = sorted(flows.items(), key=lambda kv: len(kv[1]['t']), reverse=True)[:max_flows_plot]
    if not plotted_flow_items:
        print("No plottable CWND flows found")
        return

    flow_path_metrics = {}
    if expected_flows and config_path:
        topo_path = None
        with open(config_path, 'r') as f:
            for raw in f:
                parts = raw.strip().split()
                if len(parts) >= 2 and parts[0] == 'TOPOLOGY_FILE':
                    topo_path = _resolve_config_reference(config_path, parts[1])
                    break
        if topo_path:
            flow_path_metrics = _compute_flow_path_metrics(expected_flows, topo_path, config_path)

    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    traces = []
    max_rate_gbps = 0.0
    max_win_kb = 0.0
    max_time_s = 0.0

    for idx, (flow_key, data) in enumerate(plotted_flow_items):
        label = _flow_label(flow_key, data)
        color = colors[idx % len(colors)]
        flow_start_time = _flow_start_time(flow_key, data, plot_start_time)

        rate_vals = [r / 1e9 for r in data['rate']]
        t_rate, y_rate = _filter_series_from_time(data['t'], rate_vals, flow_start_time)
        if t_rate:
            t_sub, y_sub = _subsample_series(t_rate, y_rate, max_points=120000)
            traces.append({'x': t_sub, 'y': y_sub, 'name': label, 'xaxis': 'x1', 'yaxis': 'y1', 'mode': 'lines', 'line': {'color': color}})
            max_rate_gbps = max(max_rate_gbps, max(y_rate))
            max_time_s = max(max_time_s, max(t_rate))

        win_vals = [w / 1024.0 for w in data['win']]
        t_win, y_win = _filter_series_from_time(data['t'], win_vals, flow_start_time)
        if t_win:
            t_sub, y_sub = _subsample_series(t_win, y_win, max_points=120000)
            traces.append({'x': t_sub, 'y': y_sub, 'name': label, 'xaxis': 'x2', 'yaxis': 'y2', 'mode': 'lines', 'showlegend': False, 'line': {'color': color}})
            max_win_kb = max(max_win_kb, max(y_win))
            max_time_s = max(max_time_s, max(t_win))

    for idx, (flow_key, data) in enumerate(plotted_flow_items):
        metrics = flow_path_metrics.get(flow_key)
        if not metrics:
            continue
        color = colors[idx % len(colors)]
        label = _flow_label(flow_key, data)
        traces.append({
            'x': [plot_start_time, max_time_s],
            'y': [metrics['bottleneck_bw_bps'] / 1e9, metrics['bottleneck_bw_bps'] / 1e9],
            'name': f'Line Rate {label}',
            'xaxis': 'x1',
            'yaxis': 'y1',
            'mode': 'lines',
            'line': {'color': color, 'dash': 'dot'},
        })
        traces.append({
            'x': [plot_start_time, max_time_s],
            'y': [metrics['bdp_bytes'] / 1024.0, metrics['bdp_bytes'] / 1024.0],
            'name': f'BDP {label}',
            'xaxis': 'x2',
            'yaxis': 'y2',
            'mode': 'lines',
            'showlegend': False,
            'line': {'color': color, 'dash': 'dot'},
        })

    schedules = parse_schedules(config_path)
    shapes = []
    for t, r in schedules:
        for i in [1, 2]:
            shapes.append({
                'type': 'line', 'x0': t, 'x1': t, 'y0': 0, 'y1': 1, 'yref': f'y{i} domain', 'xref': f'x{i}',
                'line': {'dash': 'dot', 'color': 'gray'}
            })

    layout = {
        'title': 'CWND and Sending Rate Analysis',
        'grid': {'rows': 2, 'columns': 1, 'pattern': 'independent'},
        'xaxis1': {'title': 'Time (s)', 'anchor': 'y1', 'rangeslider': {'visible': True, 'thickness': 0.05}, 'range': [plot_start_time, max_time_s]},
        'yaxis1': {'title': 'Sending Rate (Gbps)', 'domain': [0.56, 1.0], 'range': [0, max(max_rate_gbps * 1.1 if max_rate_gbps else 0.0, max((m['bottleneck_bw_bps'] / 1e9 for m in flow_path_metrics.values()), default=0.0) * 1.1)]},
        'xaxis2': {'title': 'Time (s)', 'anchor': 'y2', 'rangeslider': {'visible': True, 'thickness': 0.05}, 'range': [plot_start_time, max_time_s]},
        'yaxis2': {'title': 'CWND (KB)', 'domain': [0.0, 0.44], 'range': [0, max(max_win_kb * 1.25 if max_win_kb else 0.0, max((m['bdp_bytes'] / 1024.0 for m in flow_path_metrics.values()), default=0.0) * 1.25)]},
        'shapes': shapes, 'hovermode': 'x unified', 'template': 'plotly_white',
        'height': 1100, 'legend': {'orientation': 'h', 'y': -0.08}
    }
    extra_html = """
    <div class="controls">
        <label><input type="checkbox" id="lockTime" onchange="toggleLock()"> <b>Lock Time Scale</b> (Zoom all plots together)</label>
    </div>
    """
    
    extra_script = """
    var gd = document.getElementById('plot');
    var isSyncing = false;

    // Listen for zoom/pan/rangeslider events
    gd.on('plotly_relayout', function(eventData) {
        if (isSyncing || !document.getElementById('lockTime').checked) return;
        
        // Check for x-axis updates
        var keys = Object.keys(eventData);
        var xKey = keys.find(k => k.startsWith('xaxis'));
        if (!xKey) return;
        
        // Find which axis was updated to use as source
        var axisName = 'xaxis';
        if (xKey.startsWith('xaxis2')) axisName = 'xaxis2';
        
        // Get the new range from the full layout of the triggering axis
        var axisObj = gd._fullLayout[axisName];
        var newRange = axisObj.range;
        var newAuto = axisObj.autorange;
        
        isSyncing = true;
        
        var update = {
            'xaxis.range': newRange,
            'xaxis2.range': newRange,
            'xaxis.autorange': newAuto,
            'xaxis2.autorange': newAuto
        };
        
        Plotly.relayout(gd, update).then(function() {
            isSyncing = false;
        });
    });

    function toggleLock() {
        // Initial sync when checking the box
        if (document.getElementById('lockTime').checked) {
            var r = gd._fullLayout.xaxis.range;
            var a = gd._fullLayout.xaxis.autorange;
            isSyncing = true;
            Plotly.relayout(gd, {
                'xaxis.range': r, 'xaxis2.range': r,
                'xaxis.autorange': a, 'xaxis2.autorange': a
            }).then(() => isSyncing = false);
        }
    }
    """
    generate_plotly_html(traces, layout, out_path, "CWND and Sending Rate Analysis", extra_html=extra_html, extra_script=extra_script)

def plot_rx_buffer(rxbuf_path, config_path, out_path):
    """Interactive RX Buffer."""
    data = defaultdict(lambda: {'t': [], 'b': []})
    rx_context = parse_rx_buffer_context(config_path)

    parsed = parse_rxbuf_series(rxbuf_path)
    for (node, intf), series in parsed.items():
        key = f"Node {node} IF {intf}"
        data[key]['t'] = series['t']
        data[key]['b'] = [v / 1024.0 for v in series['bytes']]

    if rx_context['receiver_nodes']:
        data = defaultdict(lambda: {'t': [], 'b': []}, {
            key: value for key, value in data.items()
            if int(key.split()[1]) in rx_context['receiver_nodes']
        })

    if not data:
        print("No RX buffer samples found for receiver nodes")
        return

    traces = []
    for k, d in data.items():
        xs, bs = _subsample(d['t'], d['b'], 10000)
        traces.append({'x': xs, 'y': bs, 'name': k})
    traces.append({
        'x': [0, max((max(d['t']) for d in data.values() if d['t']), default=0.0)],
        'y': [rx_context['rx_buffer_per_queue'] / 1024.0, rx_context['rx_buffer_per_queue'] / 1024.0],
        'name': 'Per-queue limit',
        'line': {'dash': 'dash', 'color': 'red'}
    })

    schedules = parse_schedules(config_path)
    shapes = [{'type': 'line', 'x0': t, 'x1': t, 'y0': 0, 'y1': 1, 'yref': 'paper', 'line': {'dash': 'dot', 'color': 'gray'}} for t, _ in schedules]

    receiver_text = ''
    if rx_context['receiver_nodes']:
        receiver_text = f" (Receiver node(s): {', '.join(str(n) for n in sorted(rx_context['receiver_nodes']))})"

    layout = {
        'title': f'RX Buffer Occupancy{receiver_text}', 'xaxis': {'title': 'Time (s)', 'rangeslider': {'visible': True}}, 'yaxis': {'title': 'Buffer (KB)', 'range': [0, rx_context['rx_buffer_per_queue'] / 1024.0 * 1.05]},
        'shapes': shapes, 'template': 'plotly_white', 'hovermode': 'x unified'
    }
    generate_plotly_html(traces, layout, out_path, "RX Buffer Occupancy")

def plot_throughput(trace_path, config_path, out_path, bin_s=0.001, peak_envelope=False, peak_bin_s=0.0001):
    """Interactive Throughput (from binary trace)."""
    # Aggregate bytes in coarse bins; optional fine-bin peak envelope captures short bursts.
    bin_s = max(1e-6, float(bin_s))
    peak_bin_s = max(1e-6, float(peak_bin_s))
    _, node_intf_bytes, node_intf_bytes_fine = parse_switch_dequeue_bins(
        trace_path,
        bin_s,
        peak_bin_s if peak_envelope else None,
    )

    traces = []
    for (node, intf), bins in node_intf_bytes.items():
        sb = sorted(bins.keys())
        # Average rate over the coarse bin width.
        rates = [(bins[b] * 8 / bin_s / 1e9) for b in sb]
        traces.append({'x': [b*bin_s for b in sb], 'y': rates, 'name': f"Node {node} Port {intf}"})

        if node_intf_bytes_fine is not None:
            fine_bins = node_intf_bytes_fine.get((node, intf), {})
            coarse_peak = defaultdict(float)
            for fine_idx, bytes_sum in fine_bins.items():
                coarse_idx = int((fine_idx * peak_bin_s) / bin_s)
                fine_rate = bytes_sum * 8 / peak_bin_s / 1e9
                if fine_rate > coarse_peak[coarse_idx]:
                    coarse_peak[coarse_idx] = fine_rate
            if coarse_peak:
                sp = sorted(coarse_peak.keys())
                traces.append({
                    'x': [b * bin_s for b in sp],
                    'y': [coarse_peak[b] for b in sp],
                    'name': f"Node {node} Port {intf} (peak envelope)",
                    'line': {'dash': 'dot'},
                    'visible': 'legendonly'
                })

    schedules = parse_schedules(config_path)
    shapes = [{'type': 'line', 'x0': t, 'x1': t, 'y0': 0, 'y1': 1, 'yref': 'paper', 'line': {'dash': 'dot', 'color': 'gray'}} for t, _ in schedules]

    layout = {
        'title': 'Switch Port Throughput', 'xaxis': {'title': 'Time (s)', 'rangeslider': {'visible': True}}, 
        'yaxis': {'title': 'Throughput (Gbps)'}, 'shapes': shapes,
        'template': 'plotly_white', 'hovermode': 'x unified'
    }
    generate_plotly_html(traces, layout, out_path, "Switch Throughput")

def main():
    parser = argparse.ArgumentParser()
    # Base paths on script location
    script_dir = Path(__file__).parent.resolve()
    root_dir = script_dir.parent.parent
    
    parser.add_argument("--data-dir", default=str(root_dir / "results" / "data"))
    parser.add_argument("--out-dir", default=str(root_dir / "results" / "interactive_plots"))
    parser.add_argument("--config", help="Config file for annotations")
    parser.add_argument("--exp-name", default="dynamic_pull")
    parser.add_argument("--rtt-ymax", type=float, help="Fixed Y-max for RTT plot (us)")
    parser.add_argument("--throughput-bin-ms", type=float, default=1.0, help="Throughput averaging bin size in milliseconds")
    parser.add_argument("--throughput-peak-envelope", action="store_true", help="Add peak-envelope throughput traces using fine-grained bins")
    parser.add_argument("--throughput-peak-bin-ms", type=float, default=0.1, help="Fine-grained bin size in milliseconds for peak-envelope mode")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    
    # INT Queue Depth
    q_file = Path(args.data_dir) / "queue_depth.tr"
    if not q_file.exists():
        q_file = Path(args.data_dir) / "queue_depth.csv"
    if not q_file.exists():
         # Fallback to global if not in data dir
         q_file = root_dir / "simulation" / "queue_depth.tr"
         if not q_file.exists():
             q_file = root_dir / "simulation" / "queue_depth.csv"

    if q_file.exists():
        plot_queue_depth(str(q_file), args.config, os.path.join(args.out_dir, "int_queue_depth.html"))

    # CWND
    cwnd = os.path.join(args.data_dir, f"cwnd_{args.exp_name}.tr")
    if not os.path.exists(cwnd):
        cwnd = os.path.join(args.data_dir, f"cwnd_{args.exp_name}.txt")
    if os.path.exists(cwnd):
        plot_cwnd_rtt(cwnd, args.config, os.path.join(args.out_dir, "cwnd_rtt_analysis.html"), rtt_ymax=args.rtt_ymax)

    # RX Buffer
    rxbuf = os.path.join(args.data_dir, f"rxbuf_{args.exp_name}.tr")
    if not os.path.exists(rxbuf):
        rxbuf = os.path.join(args.data_dir, f"rxbuf_{args.exp_name}.txt")
    if os.path.exists(rxbuf):
        plot_rx_buffer(rxbuf, args.config, os.path.join(args.out_dir, "rx_buffer.html"))

    # Throughput
    trace = os.path.join(args.data_dir, f"mix_{args.exp_name}.tr")
    if os.path.exists(trace):
        plot_throughput(
            trace,
            args.config,
            os.path.join(args.out_dir, "switch_throughput.html"),
            bin_s=max(1e-6, args.throughput_bin_ms / 1000.0),
            peak_envelope=args.throughput_peak_envelope,
            peak_bin_s=max(1e-6, args.throughput_peak_bin_ms / 1000.0),
        )

if __name__ == "__main__":
    main()
