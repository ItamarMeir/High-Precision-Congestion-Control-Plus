#!/usr/bin/env python3
import sys
import argparse
import json
from pathlib import Path
from collections import defaultdict
import struct
from trace_parsers import parse_cwnd_ack


def _new_flow_state():
    return {
        "t": [],
        "seq": [],
        "rtt": [],
        "step": 1,
        "i": 0,
    }


def _compact_flow_preserve_extrema(flow):
    """Compact one flow while preserving key extrema samples."""
    n = len(flow["t"])
    if n <= 1:
        return

    indices = list(range(0, n, 2))
    if indices[-1] != (n - 1):
        indices.append(n - 1)

    if flow["seq"]:
        seq_max_idx = max(range(n), key=lambda i: flow["seq"][i])
        indices.append(seq_max_idx)

    valid_rtt = [(i, v) for i, v in enumerate(flow["rtt"]) if v is not None]
    if valid_rtt:
        rtt_max_idx = max(valid_rtt, key=lambda iv: iv[1])[0]
        rtt_min_idx = min(valid_rtt, key=lambda iv: iv[1])[0]
        indices.extend([rtt_max_idx, rtt_min_idx])

    indices = sorted(set(indices))
    flow["t"] = [flow["t"][i] for i in indices]
    flow["seq"] = [flow["seq"][i] for i in indices]
    flow["rtt"] = [flow["rtt"][i] for i in indices]


def _append_sampled(flow, t_s, ack_seq, rtt_us, max_points):
    # One-pass bounded decimation: append at current stride and compact when needed.
    if flow["i"] % flow["step"] == 0:
        flow["t"].append(t_s)
        flow["seq"].append(ack_seq)
        flow["rtt"].append(rtt_us)

        if len(flow["t"]) > max_points:
            _compact_flow_preserve_extrema(flow)
            flow["step"] *= 2

    flow["i"] += 1


def parse_cwnd_extra(cwnd_file, max_points_per_flow=50000, read_stride=1):
    """Parse CWND file returning flows with time, seq, and rtt."""
    flows = parse_cwnd_ack(cwnd_file, read_stride=read_stride)
    for flow in flows.values():
        while len(flow["t"]) > max_points_per_flow:
            _compact_flow_preserve_extrema(flow)
    return flows

def parse_schedules(config_file):
    """Parse config file to extract RX_PULL_RATE_SCHEDULE."""
    schedules = []
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
                        _, sched_str = parts[1].split(':', 1)
                        for entry in sched_str.split(';'):
                            if ',' in entry:
                                t_str, r_str = entry.split(',', 1)
                                t = float(t_str)
                                if t > 1000000:
                                    t /= 1e9
                                schedules.append((t, float(r_str)))
                    except Exception:
                        pass
                # Old format: node count time1 rate1 ...
                elif len(parts) >= 4:
                    try:
                        count = int(parts[2])
                        idx = 3
                        for _ in range(count):
                            if idx + 1 < len(parts):
                                t = float(parts[idx])
                                if t > 1000000:
                                    t /= 1e9
                                schedules.append((t, float(parts[idx+1])))
                                idx += 2
                    except (ValueError, IndexError):
                        pass
    return schedules

def generate_plotly_html(traces, layout, output_path, title="Interactive Plot", extra_html="", extra_script=""):
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

def plot_ack_analysis_interactive(cwnd_file, output_file, config_path=None, max_points_per_flow=50000, read_stride=1):
    flows = parse_cwnd_extra(cwnd_file, max_points_per_flow=max_points_per_flow, read_stride=read_stride)
    if not flows:
        print("ERROR: No tracking data found in CWND file. Make sure simulator logs the extra 2 columns.")
        return
        
    schedules = parse_schedules(config_path)
    traces = []
    
    for idx, (flow_key, data) in enumerate(sorted(flows.items())):
        src, dport = flow_key
        if src not in [0, 1]:
            continue
            
        seqs = data["seq"]
        unwrapped_seqs = []
        last_seq = 0
        offset = 0
        for s in seqs:
            if s < last_seq and (last_seq - s) > 1000000000:
                offset += 4294967296
            unwrapped_seqs.append(s + offset)
            last_seq = s
            
        label = f"Sender {src} (port {dport})"
        
        # Plot 1: Stevens Plot (Sequence Number vs Time)
        traces.append({
            'x': data["t"], 'y': unwrapped_seqs, 'name': f"{label} (Seq)",
            'xaxis': 'x1', 'yaxis': 'y1', 'mode': 'lines'
        })
        
        # Plot 2: Real Measured RTT vs Time
        valid_t = [t for t, r in zip(data["t"], data["rtt"]) if r is not None]
        valid_r = [r for r in data["rtt"] if r is not None]
        
        traces.append({
            'x': valid_t, 'y': valid_r, 'name': f"{label} (RTT)",
            'xaxis': 'x2', 'yaxis': 'y2', 'mode': 'lines'
        })

    shapes = []
    for t, r in schedules:
        for i in [1, 2]:
            shapes.append({
                'type': 'line', 'x0': t, 'x1': t, 'y0': 0, 'y1': 1, 'yref': f'y{i} domain', 'xref': f'x{i}',
                'line': {'dash': 'dot', 'color': 'gray'}
            })

    layout = {
        'title': 'Interactive ACK Level Flow Analysis',
        'grid': {'rows': 2, 'columns': 1, 'pattern': 'independent'},
        'xaxis1': {'title': 'Time (s)', 'anchor': 'y1', 'rangeslider': {'visible': True, 'thickness': 0.05}}, 
        'yaxis1': {'title': 'ACK Sequence Number', 'domain': [0.55, 1.0], 'autorange': True},
        'xaxis2': {'title': 'Time (s)', 'anchor': 'y2', 'rangeslider': {'visible': True, 'thickness': 0.05}}, 
        'yaxis2': {'title': 'Measured RTT (us)', 'domain': [0.0, 0.45], 'autorange': True},
        'shapes': shapes, 'hovermode': 'x unified', 'template': 'plotly_white',
        'height': 1000, 'legend': {'orientation': 'h', 'y': -0.1}
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
    
    generate_plotly_html(traces, layout, output_file, "Interactive ACK Analysis", extra_html=extra_html, extra_script=extra_script)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Interactive ACK analysis")
    parser.add_argument("cwnd_file", help="Input CWND text file")
    parser.add_argument("output_file", nargs="?", help="Output HTML file")
    parser.add_argument("config_path", nargs="?", help="Configuration file path")
    parser.add_argument("--max-points-per-flow", type=int, default=50000,
                        help="Bounded sampled points per flow to prevent browser hangs")
    parser.add_argument("--read-stride", type=int, default=1,
                        help="Read every Nth record to speed up very large traces")
    args = parser.parse_args()

    output_file = args.output_file if args.output_file else args.cwnd_file.replace('.txt', '_ack_analysis.html')
    plot_ack_analysis_interactive(
        args.cwnd_file,
        output_file,
        config_path=args.config_path,
        max_points_per_flow=args.max_points_per_flow,
        read_stride=max(1, args.read_stride),
    )
