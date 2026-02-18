#!/usr/bin/env python3
"""Unified script to generate interactive HTML plots for simulation data using Plotly.js.

Supported plots:
- INT Queue Depth (from queue_depth.csv)
- CWND/Rate/RTT (from cwnd_*.txt)
- RX Buffer (from rxbuf_*.txt)
- Switch Throughput (from binary *.tr)
- Flow Completion Time (from fct_*.txt)
"""
import argparse
import csv
import json
import os
import struct
import ctypes
from collections import defaultdict
from pathlib import Path

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
                try:
                    idx = parts.index('RX_PULL_RATE_SCHEDULE') + 2 # Skip keyword and node_id
                    count = int(parts[idx])
                    idx += 1
                    for _ in range(count):
                        t, r = float(parts[idx]), float(parts[idx+1])
                        schedules.append((t, r))
                        idx += 2
                except (ValueError, IndexError): continue
    return schedules

# --- Plot Specific Functions ---

def plot_queue_depth(csv_path, config_path, out_path):
    """Interactive INT Queue Depth with side-by-side CDF."""
    qp_data = defaultdict(lambda: {'t': [], 'q': []})
    max_bins = defaultdict(int)
    all_qlens = []
    bin_s = 0.0001
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t, q = float(row['Time']), int(row['Qlen'])
                key = f"QP {row['QpId']} Hop {row['Hop']}"
                qp_data[key]['t'].append(t)
                qp_data[key]['q'].append(q)
                all_qlens.append(q)
                b = int(t / bin_s)
                if q > max_bins[b]: max_bins[b] = q
            except (KeyError, ValueError): continue

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
        traces.append({
            'x': data['t'], 'y': data['q'], 'name': key, 
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
    """Interactive CWND/Rate/RTT 3-panel dashboard."""
    flows = defaultdict(lambda: {'t': [], 'rate': [], 'win': [], 'rtt': []})
    with open(cwnd_path, 'r') as f:
        for line in f:
            p = line.split()
            if len(p) < 7: continue
            try:
                t, rate, win = int(p[0])/1e9, int(p[5]), int(p[6])
                key = f"{p[1]}->{p[2]} ({p[3]}:{p[4]})"
                flows[key]['t'].append(t)
                flows[key]['rate'].append(rate / 1e9) # Gbps
                flows[key]['win'].append(win / 1000) # KB
                # RTT calculation (in microseconds)
                if rate > 0: 
                    # rate is in bps, win is in bytes. RTT = (win*8) / rate
                    rtt = (win * 8) / (rate / 1e6)
                    flows[key]['rtt'].append(rtt)
                else: 
                    flows[key]['rtt'].append(None)
            except ValueError: continue

    traces = []
    # Panel 1: Rate, Panel 2: Window, Panel 3: RTT
    for key, data in flows.items():
        # Rate
        traces.append({'x': data['t'], 'y': data['rate'], 'name': f"{key} Rate (Gbps)", 'xaxis': 'x1', 'yaxis': 'y1'})
        # Window
        traces.append({'x': data['t'], 'y': data['win'], 'name': f"{key} Window (KB)", 'xaxis': 'x2', 'yaxis': 'y2'})
        # RTT
        traces.append({'x': data['t'], 'y': data['rtt'], 'name': f"{key} RTT (us)", 'xaxis': 'x3', 'yaxis': 'y3'})

    schedules = parse_schedules(config_path)
    shapes = []
    for t, r in schedules:
        for i in [1, 2, 3]:
            shapes.append({
                'type': 'line', 'x0': t, 'x1': t, 'y0': 0, 'y1': 1, 'yref': f'y{i} domain', 'xref': f'x{i}',
                'line': {'dash': 'dot', 'color': 'gray'}
            })

    layout = {
        'title': 'Rate, Window, and RTT Analysis (Independent Views)',
        'grid': {'rows': 3, 'columns': 1, 'pattern': 'independent'},
        # Top Panel: Rate
        'xaxis1': {'title': 'Time (s)', 'anchor': 'y1', 'rangeslider': {'visible': True, 'thickness': 0.05}}, 
        'yaxis1': {'title': 'Rate (Gbps)', 'domain': [0.70, 0.95], 'autorange': True},
        # Middle Panel: Window
        'xaxis2': {'title': 'Time (s)', 'anchor': 'y2', 'rangeslider': {'visible': True, 'thickness': 0.05}}, 
        'yaxis2': {'title': 'Window (KB)', 'domain': [0.35, 0.60], 'autorange': True},
        # Bottom Panel: RTT
        'xaxis3': {'title': 'Time (s)', 'anchor': 'y3', 'rangeslider': {'visible': True, 'thickness': 0.05}}, 
        'yaxis3': {'title': 'RTT (us)', 'domain': [0.00, 0.25], 'autorange': rtt_ymax is None, 'range': [0, rtt_ymax] if rtt_ymax else None},
        'shapes': shapes, 'hovermode': 'x unified', 'template': 'plotly_white',
        'height': 1400, 'legend': {'orientation': 'h', 'y': -0.05}
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
        else if (xKey.startsWith('xaxis3')) axisName = 'xaxis3';
        
        // Get the new range from the full layout of the triggering axis
        var axisObj = gd._fullLayout[axisName];
        var newRange = axisObj.range;
        var newAuto = axisObj.autorange;
        
        isSyncing = true;
        
        var update = {
            'xaxis.range': newRange,
            'xaxis2.range': newRange,
            'xaxis3.range': newRange,
            'xaxis.autorange': newAuto,
            'xaxis2.autorange': newAuto,
            'xaxis3.autorange': newAuto
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
                'xaxis.range': r, 'xaxis2.range': r, 'xaxis3.range': r,
                'xaxis.autorange': a, 'xaxis2.autorange': a, 'xaxis3.autorange': a
            }).then(() => isSyncing = false);
        }
    }
    """
    generate_plotly_html(traces, layout, out_path, "CWND/Rate/RTT Analysis", extra_html=extra_html, extra_script=extra_script)

def plot_rx_buffer(rxbuf_path, config_path, out_path):
    """Interactive RX Buffer."""
    data = defaultdict(lambda: {'t': [], 'b': []})
    with open(rxbuf_path, 'r') as f:
        for line in f:
            p = line.split()
            if len(p) < 4: continue
            try:
                t, node, b = int(p[0])/1e9, int(p[1]), int(p[3])
                data[f"Node {node} IF {p[2]}"]['t'].append(t)
                data[f"Node {node} IF {p[2]}"]['b'].append(b / 1000)
            except ValueError: continue

    traces = [{'x': d['t'], 'y': d['b'], 'name': k} for k, d in data.items()]
    schedules = parse_schedules(config_path)
    shapes = [{'type': 'line', 'x0': t, 'x1': t, 'y0': 0, 'y1': 1, 'yref': 'paper', 'line': {'dash': 'dot', 'color': 'gray'}} for t, _ in schedules]

    layout = {
        'title': 'RX Buffer Occupancy', 'xaxis': {'title': 'Time (s)', 'rangeslider': {'visible': True}}, 'yaxis': {'title': 'Buffer (KB)'},
        'shapes': shapes, 'template': 'plotly_white', 'hovermode': 'x unified'
    }
    generate_plotly_html(traces, layout, out_path, "RX Buffer Occupancy")

def plot_throughput(trace_path, config_path, out_path):
    """Interactive Throughput (from binary trace)."""
    # This is complex, we aggregate bytes in bins
    bin_s = 0.001 # 1ms bins
    node_intf_bytes = defaultdict(lambda: defaultdict(int))
    
    with open(trace_path, "rb") as f:
        # Skip SimSetting header
        try:
            raw_count = f.read(4)
            if not raw_count: return
            (count,) = struct.unpack("<I", raw_count)
            f.read(count * 11 + 4) # Skip node/intf/bps and SimSetting.win
        except (struct.error, ValueError): return
        
        entry_size = ctypes.sizeof(Trace)
        while True:
            chunk = f.read(entry_size)
            if not chunk or len(chunk) < entry_size: break
            t = Trace.from_buffer_copy(chunk)
            # Match plot_switch_throughput.py: nodeType=1 (Switch), event=2 (Dequeue)
            if t.nodeType == 1 and t.event == 2:
                bin_idx = int((t.time/1e9) / bin_s)
                node_intf_bytes[(t.node, t.intf)][bin_idx] += t.size

    traces = []
    for (node, intf), bins in node_intf_bytes.items():
        sb = sorted(bins.keys())
        # Rate = bytes * 8 / bin_duration / 1e9 (Gbps)
        rates = [(bins[b] * 8 / bin_s / 1e9) for b in sb]
        traces.append({'x': [b*bin_s for b in sb], 'y': rates, 'name': f"Node {node} Port {intf}"})

    schedules = parse_schedules(config_path)
    shapes = [{'type': 'line', 'x0': t, 'x1': t, 'y0': 0, 'y1': 1, 'yref': 'paper', 'line': {'dash': 'dot', 'color': 'gray'}} for t, _ in schedules]

    layout = {
        'title': 'Switch Port Throughput', 'xaxis': {'title': 'Time (s)', 'rangeslider': {'visible': True}}, 
        'yaxis': {'title': 'Throughput (Gbps)'}, 'shapes': shapes,
        'template': 'plotly_white', 'hovermode': 'x unified'
    }
    generate_plotly_html(traces, layout, out_path, "Switch Throughput")

def plot_fct(fct_path, out_path):
    """Interactive FCT vs Flow Size."""
    data = []
    with open(fct_path, 'r') as f:
        for line in f:
            p = line.split()
            if len(p) < 8: continue
            try:
                # src dst sport dport base_fct start end size
                src, dst, sp, dp = p[0], p[1], p[2], p[3]
                base_fct = int(p[4])
                start, end = int(p[5]), int(p[6])
                size = int(p[7])
                fct = end - start
                if fct <= 0: fct = end # fallback
                slowdown = fct / base_fct if base_fct > 0 else 1.0
                data.append({
                    'size': size, 'fct': fct / 1e6, 'slowdown': slowdown,
                    'info': f"{src}->{dst} ({sp}:{dp}) Size: {size}B"
                })
            except ValueError: continue

    if not data: return

    traces = [
        {
            'x': [d['size'] for d in data],
            'y': [d['fct'] for d in data],
            'text': [d['info'] for d in data],
            'mode': 'markers', 'name': 'FCT (ms)',
            'marker': {'opacity': 0.6, 'size': 8}
        },
        {
            'x': [d['size'] for d in data],
            'y': [d['slowdown'] for d in data],
            'text': [d['info'] for d in data],
            'mode': 'markers', 'name': 'Slowdown',
            'yaxis': 'y2', 'visible': 'legendonly'
        }
    ]

    layout = {
        'title': 'Flow Completion Time vs Size',
        'xaxis': {'title': 'Flow Size (bytes)', 'type': 'log'},
        'yaxis': {'title': 'FCT (ms)', 'type': 'log'},
        'yaxis2': {'title': 'Slowdown', 'overlaying': 'y', 'side': 'right', 'type': 'log'},
        'hovermode': 'closest', 'template': 'plotly_white'
    }
    generate_plotly_html(traces, layout, out_path, "FCT Analysis")

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
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    
    # INT Queue Depth
    q_csv = Path(args.data_dir) / "queue_depth.csv"
    if not q_csv.exists():
         # Fallback to global if not in data dir (though run_all_plots should handle copying or setup)
         q_csv = root_dir / "simulation" / "queue_depth.csv"

    if q_csv.exists():
        plot_queue_depth(str(q_csv), args.config, os.path.join(args.out_dir, "int_queue_depth.html"))

    # CWND
    cwnd = os.path.join(args.data_dir, f"cwnd_{args.exp_name}.txt")
    if os.path.exists(cwnd):
        plot_cwnd_rtt(cwnd, args.config, os.path.join(args.out_dir, "cwnd_rtt_analysis.html"), rtt_ymax=args.rtt_ymax)

    # RX Buffer
    rxbuf = os.path.join(args.data_dir, f"rxbuf_{args.exp_name}.txt")
    if os.path.exists(rxbuf):
        plot_rx_buffer(rxbuf, args.config, os.path.join(args.out_dir, "rx_buffer.html"))

    # Throughput
    trace = os.path.join(args.data_dir, f"mix_{args.exp_name}.tr")
    if os.path.exists(trace):
        plot_throughput(trace, args.config, os.path.join(args.out_dir, "switch_throughput.html"))

    # FCT
    fct = os.path.join(args.data_dir, f"fct_{args.exp_name}.txt")
    if os.path.exists(fct):
        plot_fct(fct, os.path.join(args.out_dir, "fct.html"))

if __name__ == "__main__":
    main()
