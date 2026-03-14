#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path


def parse_schedules(config_file):
    schedules = []
    if not config_file or not Path(config_file).exists():
        return schedules

    with open(config_file, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if parts[0] != 'RX_PULL_RATE_SCHEDULE' or len(parts) < 4:
                continue
            try:
                count = int(parts[2])
            except ValueError:
                continue
            idx = 3
            for _ in range(count):
                if idx + 1 >= len(parts):
                    break
                try:
                    schedules.append((float(parts[idx]), float(parts[idx + 1])))
                except ValueError:
                    pass
                idx += 2
    return schedules


def load_rows(trace_file):
    rows = []
    with open(trace_file, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('time_ns'):
                continue
            parts = line.split()
            if len(parts) < 11:
                continue
            try:
                rows.append({
                    'time_ns': int(parts[0]),
                    'qp_id': int(parts[1]),
                    'src': int(parts[2]),
                    'dst': int(parts[3]),
                    'sport': int(parts[4]),
                    'dport': int(parts[5]),
                    'cc_mode': int(parts[6]),
                    'u_max': float(parts[7]),
                    'r_delivered_bps': float(parts[8]),
                    'c_host_bps': float(parts[9]),
                    'u_host': float(parts[10]),
                })
            except ValueError:
                continue
    return rows


def group_by_qp(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['qp_id']].append(row)
    for qp_rows in grouped.values():
        qp_rows.sort(key=lambda r: r['time_ns'])
    return grouped


def subsample_rows(rows, max_points=10000, value_fn=None):
    if len(rows) <= max_points:
        return rows
    step = max(1, len(rows) // max_points)
    indices = list(range(0, len(rows), step))
    if indices[-1] != len(rows) - 1:
        indices.append(len(rows) - 1)

    if value_fn is not None:
        values = []
        for idx, row in enumerate(rows):
            v = value_fn(row)
            if v is None:
                continue
            values.append((idx, v))
        if values:
            indices.append(max(values, key=lambda iv: iv[1])[0])
            indices.append(min(values, key=lambda iv: iv[1])[0])

    indices = sorted(set(indices))
    return [rows[i] for i in indices]


def label(rows):
    first = rows[0]
    return f"{first['src']}->{first['dst']} ({first['sport']}:{first['dport']})"


def generate_plotly_html(traces, layout, output_path, title='Interactive Plot', extra_html='', extra_script=''):
    config = {'responsive': True, 'displayModeBar': True, 'scrollZoom': True}
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset=\"utf-8\">
    <title>{title}</title>
    <script src=\"https://cdn.plot.ly/plotly-2.27.0.min.js\"></script>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
        #plot {{ width: 100%; height: 88vh; min-height: 700px; }}
        .help {{ color: #666; font-size: 13px; padding: 10px 0; }}
        .controls {{ margin-bottom: 10px; padding: 10px; background: white; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    {extra_html}
    <div id=\"plot\"></div>
    <div class=\"help\"><b>Controls:</b> Drag to zoom &bull; Double-click to reset &bull; Scroll to zoom &bull; Legend items toggle traces</div>
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


def build_interactive_plot(trace_file, output_file, config_file=None):
    rows = load_rows(trace_file)
    if not rows:
        raise RuntimeError('No utilization rows found')

    grouped = group_by_qp(rows)
    schedules = parse_schedules(config_file)
    cc_modes = {row['cc_mode'] for row in rows}
    is_hpcc_plus = 11 in cc_modes
    min_time_s = min(row['time_ns'] for row in rows) / 1e9
    max_time_s = max(row['time_ns'] for row in rows) / 1e9

    if is_hpcc_plus:
        metric_specs = [
            ('u_max', 'U_max', 1.0, 'y1', 'x1', [0.78, 1.0]),
            ('r_delivered_bps', 'R_delivered (Gbps)', 1e-9, 'y2', 'x2', [0.52, 0.74]),
            ('c_host_bps', 'C_host (Gbps)', 1e-9, 'y3', 'x3', [0.26, 0.48]),
            ('u_host', 'u_host', 1.0, 'y4', 'x4', [0.0, 0.22]),
        ]
        title = 'Interactive HPCC+ Utilization Metrics'
        height = 1500
    else:
        metric_specs = [('u_max', 'U_max', 1.0, 'y1', 'x1', [0.0, 1.0])]
        title = 'Interactive HPCC Utilization Metrics'
        height = 700

    traces = []
    for field, _, scale, yaxis, xaxis, _ in metric_specs:
        for _, qp_rows in sorted(grouped.items()):
            sampled = subsample_rows(
                qp_rows,
                value_fn=(lambda row, f=field: row[f] if (f == 'u_max' or row[f] >= 0) else None),
            )
            xs = []
            ys = []
            for row in sampled:
                value = row[field]
                if field != 'u_max' and value < 0:
                    continue
                xs.append(row['time_ns'] / 1e9)
                ys.append(value * scale)
            if not xs:
                continue
            traces.append({
                'x': xs,
                'y': ys,
                'name': f"{label(qp_rows)} [{field}]",
                'mode': 'lines',
                'xaxis': xaxis,
                'yaxis': yaxis,
            })

    shapes = []
    annotations = []
    xrefs = [spec[4] for spec in metric_specs]
    for t, r in schedules:
        for xref in xrefs:
            shapes.append({
                'type': 'line',
                'x0': t, 'x1': t,
                'y0': 0, 'y1': 1,
                'yref': 'paper',
                'xref': xref,
                'line': {'dash': 'dot', 'color': 'gray'}
            })
        annotations.append({
            'x': t,
            'y': 1.02,
            'yref': 'paper',
            'xref': 'x1',
            'text': f'{r:g}',
            'showarrow': False,
            'font': {'size': 9, 'color': 'gray'},
            'xanchor': 'left',
        })

    layout = {
        'title': title,
        'template': 'plotly_white',
        'hovermode': 'x unified',
        'height': height,
        'legend': {'orientation': 'h', 'y': -0.06},
        'shapes': shapes,
        'annotations': annotations,
    }

    for idx, (_, ylabel, _, yaxis, xaxis, domain) in enumerate(metric_specs, start=1):
        layout[f'xaxis{idx}'] = {
            'title': 'Time (s)',
            'anchor': yaxis,
            'range': [min_time_s, max_time_s],
            'rangeslider': {'visible': True, 'thickness': 0.04},
        }
        layout[f'yaxis{idx}'] = {
            'title': ylabel,
            'domain': domain,
            'autorange': True,
            'rangemode': 'tozero',
        }

    extra_html = """
    <div class=\"controls\">
        <label><input type=\"checkbox\" id=\"lockTime\" onchange=\"toggleLock()\" checked> <b>Lock Time Scale</b> (Zoom all plots together)</label>
    </div>
    """

    if is_hpcc_plus:
        axis_names = ['xaxis', 'xaxis2', 'xaxis3', 'xaxis4']
    else:
        axis_names = ['xaxis']
    axis_range_updates = ', '.join([f"'{axis}.range': newRange" for axis in axis_names])
    axis_auto_updates = ', '.join([f"'{axis}.autorange': newAuto" for axis in axis_names])
    init_axis_updates = ', '.join([f"'{axis}.range': r, '{axis}.autorange': a" for axis in axis_names])

    extra_script = f"""
    var gd = document.getElementById('plot');
    var isSyncing = false;

    gd.on('plotly_relayout', function(eventData) {{
        if (isSyncing || !document.getElementById('lockTime').checked) return;
        var keys = Object.keys(eventData);
        var xKey = keys.find(k => k.startsWith('xaxis'));
        if (!xKey) return;

        var axisName = 'xaxis';
        if (xKey.startsWith('xaxis2')) axisName = 'xaxis2';
        else if (xKey.startsWith('xaxis3')) axisName = 'xaxis3';
        else if (xKey.startsWith('xaxis4')) axisName = 'xaxis4';

        var axisObj = gd._fullLayout[axisName];
        var newRange = axisObj.range;
        var newAuto = axisObj.autorange;

        isSyncing = true;
        Plotly.relayout(gd, {{{axis_range_updates}, {axis_auto_updates}}}).then(function() {{
            isSyncing = false;
        }});
    }});

    function toggleLock() {{
        if (document.getElementById('lockTime').checked) {{
            var r = gd._fullLayout.xaxis.range;
            var a = gd._fullLayout.xaxis.autorange;
            isSyncing = true;
            Plotly.relayout(gd, {{{init_axis_updates}}}).then(function() {{ isSyncing = false; }});
        }}
    }}
    """

    generate_plotly_html(traces, layout, output_file, title, extra_html=extra_html, extra_script=extra_script)


def main():
    parser = argparse.ArgumentParser(description='Generate interactive utilization metrics plot')
    parser.add_argument('trace_file', help='Input utilization trace file')
    parser.add_argument('output_file', help='Output HTML file')
    parser.add_argument('config_file', nargs='?', default=None, help='Optional config file')
    args = parser.parse_args()
    build_interactive_plot(args.trace_file, args.output_file, args.config_file)


if __name__ == '__main__':
    main()