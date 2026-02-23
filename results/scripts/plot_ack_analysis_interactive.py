#!/usr/bin/env python3
import sys
import argparse
import json
from pathlib import Path
from collections import defaultdict

def parse_cwnd_extra(cwnd_file):
    """Parse CWND file returning flows with time, seq, and rtt."""
    flows = defaultdict(lambda: {"t": [], "seq": [], "rtt": []})
    
    with open(cwnd_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 9:
                continue
            try:
                t_ns = int(parts[0])
                src = int(parts[1])
                dst = int(parts[2])
                sport = int(parts[3])
                dport = int(parts[4])
                
                lastRtt = int(parts[7])
                lastAckSeq = int(parts[8])
                
                key = (src, dport)
                flows[key]["t"].append(t_ns / 1e9)
                flows[key]["seq"].append(lastAckSeq)
                if lastRtt < 100000000:
                    flows[key]["rtt"].append(lastRtt / 1000.0)
                else:
                    flows[key]["rtt"].append(None)
            except (ValueError, IndexError):
                pass
                
    return flows

def parse_schedules(config_file):
    """Parse config file to extract RX_PULL_RATE_SCHEDULE."""
    schedules = []
    if not config_file or not Path(config_file).exists():
        return schedules
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'): continue
            if 'RX_PULL_RATE_SCHEDULE' in line:
                parts = line.split()
                try:
                    idx = parts.index('RX_PULL_RATE_SCHEDULE') + 2
                    count = int(parts[idx])
                    idx += 1
                    for _ in range(count):
                        t, r = float(parts[idx]), float(parts[idx+1])
                        schedules.append((t, r))
                        idx += 2
                except (ValueError, IndexError): continue
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

def plot_ack_analysis_interactive(cwnd_file, output_file, config_path=None):
    flows = parse_cwnd_extra(cwnd_file)
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
    args = parser.parse_args()
    
    output_file = args.output_file if args.output_file else args.cwnd_file.replace('.txt', '_ack_analysis.html')
    plot_ack_analysis_interactive(args.cwnd_file, output_file, config_path=args.config_path)
