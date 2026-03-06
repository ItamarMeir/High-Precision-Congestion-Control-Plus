#!/usr/bin/env python3
"""Generate an interactive HTML plot of INT queue depth data using Plotly.js (CDN).

Usage:
    python3 plot_queue_depth_interactive.py [queue_depth.csv] [--config config.txt] [--out output.html]

The output HTML file is fully self-contained (uses CDN) and can be opened in any browser.
Supports: zoom, pan, box-select, hover tooltips, and double-click to reset view.
"""
import argparse
import csv
import json
import os
import re
from collections import defaultdict


def parse_schedules(config_path):
    """Parse RX_PULL_RATE_SCHEDULE from config file."""
    schedules = []
    if not config_path or not os.path.exists(config_path):
        return schedules
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            if 'RX_PULL_RATE_SCHEDULE' in line:
                parts = line.split()
                idx = parts.index('RX_PULL_RATE_SCHEDULE') + 1
                # Skip <node_id>
                idx += 1 
                count = int(parts[idx])
                idx += 1
                for _ in range(count):
                    t = float(parts[idx])
                    r = float(parts[idx + 1])
                    schedules.append((t, r))
                    idx += 2
    return schedules


def parse_int_hop_metadata(config_path):
    """Return CC mode and configured switch-hop count from a config file."""
    meta = {'cc_mode': None, 'switch_hops': None}
    if not config_path or not os.path.exists(config_path):
        return meta
    with open(config_path) as f:
        for raw in f:
            line = raw.strip()
            if line.startswith('#') or not line:
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


def parse_queue_depth_csv(csv_path, config_path=None):
    """Parse queue_depth.csv and return per-QP time series."""
    qp_data = defaultdict(lambda: {'times': [], 'qlens': []})
    hop_meta = parse_int_hop_metadata(config_path)
    allowed_hops = None
    if hop_meta.get('cc_mode') == 11 and hop_meta.get('switch_hops') is not None:
        allowed_hops = set(range(hop_meta['switch_hops']))
    
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            try:
                t = float(row[0])
                qp_id = row[1]
                hop = int(row[2])
                if allowed_hops is not None and hop not in allowed_hops:
                    continue
                qlen = int(row[3])
                key = f"QP {qp_id} Hop {hop}"
                qp_data[key]['times'].append(t)
                qp_data[key]['qlens'].append(qlen)
            except (ValueError, IndexError):
                continue

    # Also create a combined "max across QPs" trace, binned to 0.1ms
    bin_s = 0.0001  # 0.1ms bins
    max_bins = defaultdict(int)
    for key, data in qp_data.items():
        for t, q in zip(data['times'], data['qlens']):
            b = int(t / bin_s)
            if q > max_bins[b]:
                max_bins[b] = q

    if max_bins:
        sorted_bins = sorted(max_bins.keys())
        combined_times = [b * bin_s for b in sorted_bins]
        combined_qlens = [max_bins[b] for b in sorted_bins]
    else:
        combined_times, combined_qlens = [], []

    return qp_data, combined_times, combined_qlens


def generate_html(qp_data, combined_times, combined_qlens, schedules, output_path):
    """Generate interactive Plotly HTML."""
    
    traces_js = []

    # Combined trace (default visible)
    traces_js.append({
        'x': combined_times,
        'y': combined_qlens,
        'type': 'scatter',
        'mode': 'lines',
        'name': 'Max Queue Depth (all QPs)',
        'line': {'color': '#e74c3c', 'width': 1},
        'fill': 'tozeroy',
        'fillcolor': 'rgba(231, 76, 60, 0.2)',
    })

    # Per-QP traces (hidden by default)
    colors = ['#3498db', '#f39c12', '#2ecc71', '#9b59b6', '#1abc9c']
    for i, (key, data) in enumerate(qp_data.items()):
        traces_js.append({
            'x': data['times'],
            'y': data['qlens'],
            'type': 'scatter',
            'mode': 'lines',
            'name': key,
            'line': {'color': colors[i % len(colors)], 'width': 0.8},
            'visible': 'legendonly',
        })

    # Schedule annotation shapes
    shapes = []
    annotations = []
    for t, r in schedules:
        shapes.append({
            'type': 'line',
            'x0': t, 'x1': t,
            'y0': 0, 'y1': 1,
            'yref': 'paper',
            'line': {'color': 'gray', 'width': 1.5, 'dash': 'dot'},
        })
        annotations.append({
            'x': t,
            'y': 1.02,
            'yref': 'paper',
            'text': f't={t}s<br>Rate={r}',
            'showarrow': False,
            'font': {'size': 9, 'color': 'gray'},
            'xanchor': 'left',
        })

    layout = {
        'title': {
            'text': 'INT Instantaneous Queue Depth (Interactive)',
            'font': {'size': 16},
        },
        'xaxis': {
            'title': 'Time (s)',
            'rangeslider': {'visible': True, 'thickness': 0.08},
            'type': 'linear',
        },
        'yaxis': {
            'title': 'Queue Depth (bytes)',
            'rangemode': 'tozero',
        },
        'shapes': shapes,
        'annotations': annotations,
        'hovermode': 'x unified',
        'template': 'plotly_white',
        'legend': {
            'orientation': 'h',
            'yanchor': 'bottom',
            'y': -0.3,
            'xanchor': 'center',
            'x': 0.5,
        },
        'margin': {'b': 120},
    }

    config = {
        'responsive': True,
        'displayModeBar': True,
        'modeBarButtonsToAdd': ['drawrect', 'eraseshape'],
        'scrollZoom': True,
    }

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>INT Queue Depth - Interactive</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
        #plot {{ width: 100%; height: 80vh; min-height: 500px; }}
        .help {{ color: #666; font-size: 13px; padding: 10px 0; }}
        .help kbd {{ background: #eee; padding: 2px 6px; border-radius: 3px; border: 1px solid #ccc; font-size: 11px; }}
    </style>
</head>
<body>
    <div id="plot"></div>
    <div class="help">
        <b>Controls:</b>
        Drag to zoom &bull; Double-click to reset &bull; Scroll to zoom &bull; 
        Use the range slider at the bottom to navigate &bull;
        Click legend items to toggle traces &bull;
        Hover for exact values
    </div>
    <script>
        var traces = {json.dumps(traces_js)};
        var layout = {json.dumps(layout)};
        var config = {json.dumps(config)};
        Plotly.newPlot('plot', traces, layout, config);
    </script>
</body>
</html>"""

    with open(output_path, 'w') as f:
        f.write(html)
    print(f"Interactive plot saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate interactive INT queue depth plot")
    parser.add_argument("input", nargs="?", default="simulation/queue_depth.csv",
                        help="Path to queue_depth.csv")
    parser.add_argument("--config", default=None, help="Config file for schedule annotations")
    parser.add_argument("--out", default=None, help="Output HTML file path")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found")
        return

    output = args.out or os.path.splitext(args.input)[0] + "_interactive.html"
    
    schedules = parse_schedules(args.config)
    qp_data, combined_times, combined_qlens = parse_queue_depth_csv(args.input, args.config)
    generate_html(qp_data, combined_times, combined_qlens, schedules, output)


if __name__ == "__main__":
    main()
