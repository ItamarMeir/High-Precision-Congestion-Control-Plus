#!/usr/bin/env python3
"""Plot compact HPCC and HPCC+ utilization traces."""

import argparse
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


def _parse_schedules(config_file):
    schedules = []
    if not config_file or not Path(config_file).exists():
        return schedules

    with open(config_file, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] != "RX_PULL_RATE_SCHEDULE" or len(parts) < 4:
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


def _load_rows(trace_file):
    rows = []
    with open(trace_file, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("time_ns"):
                continue
            parts = line.split()
            if len(parts) < 11:
                continue
            try:
                rows.append({
                    "time_ns": int(parts[0]),
                    "qp_id": int(parts[1]),
                    "src": int(parts[2]),
                    "dst": int(parts[3]),
                    "sport": int(parts[4]),
                    "dport": int(parts[5]),
                    "cc_mode": int(parts[6]),
                    "u_max": float(parts[7]),
                    "r_delivered_bps": float(parts[8]),
                    "c_host_bps": float(parts[9]),
                    "u_host": float(parts[10]),
                })
            except ValueError:
                continue
    return rows


def _group_by_qp(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["qp_id"]].append(row)
    for qp_rows in grouped.values():
        qp_rows.sort(key=lambda r: r["time_ns"])
    return grouped


def _subsample(rows, max_points=4000):
    if len(rows) <= max_points:
        return rows
    step = max(1, len(rows) // max_points)
    sampled = rows[::step]
    if sampled[-1] is not rows[-1]:
        sampled.append(rows[-1])
    return sampled


def _draw_schedule_lines(ax, schedules):
    if not schedules:
        return
    ymax = ax.get_ylim()[1]
    for time_s, rate in schedules:
        ax.axvline(x=time_s, color="gray", linestyle=":", alpha=0.7, linewidth=1.0)
        ax.text(time_s, ymax * 0.98, f"{rate:g}", rotation=90, va="top", ha="left", fontsize=7, color="gray")


def _label(rows):
    first = rows[0]
    return f"{first['src']}->{first['dst']} ({first['sport']}:{first['dport']})"


def plot_trace(trace_file, out_path, config_file=None):
    rows = _load_rows(trace_file)
    if not rows:
        raise RuntimeError("No utilization rows found")

    grouped = _group_by_qp(rows)
    schedules = _parse_schedules(config_file)
    cc_modes = {row["cc_mode"] for row in rows}
    is_hpcc_plus = 11 in cc_modes
    min_time_s = min(row["time_ns"] for row in rows) / 1e9
    max_time_s = max(row["time_ns"] for row in rows) / 1e9

    # Load high-res u_switch if exists
    hires_data = defaultdict(list)
    uswitch_path = Path(trace_file).parent / "debug_uswitch.txt"
    if uswitch_path.exists():
        print(f"Loading high-res u_switch from {uswitch_path}")
        with open(uswitch_path, "r") as f:
            for line in f:
                p = line.split()
                if len(p) >= 3:
                    # ns, sid, u
                    hires_data[int(p[1])].append((int(p[0])/1e9, float(p[2])))

    if is_hpcc_plus:
        # 4 plots: U_max, R_delivered, C_host, u_host
        fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True)
        axes = [ax for row in axes for ax in row]
        metric_specs = [
            ("u_max", "U_max (INT max)", 1.0, "trace"),
            ("r_delivered_bps", "R_delivered (Gb/s)", 1e-9, "trace"),
            ("c_host_bps", "C_host (Gb/s)", 1e-9, "trace"),
            ("u_host", "u_host (INT host)", 1.0, "trace"),
        ]
        title = "HPCC+ Utilization Metrics"
    else:
        fig, ax = plt.subplots(1, 1, figsize=(12, 4.5))
        axes = [ax]
        metric_specs = [("u_max", "U_max", 1.0, "trace")]
        title = "HPCC Utilization Metric"

    for axis, (field, ylabel, scale, source) in zip(axes, metric_specs):
        max_y = 0
        if source == "trace":
            for qp_id, qp_rows in sorted(grouped.items()):
                sampled = _subsample(qp_rows)
                times = [row["time_ns"] / 1e9 for row in sampled]
                values = []
                filtered_times = []
                for time_s, row in zip(times, sampled):
                    value = row[field]
                    # Don't skip R_delivered if it's 0 (it might be -1 early on)
                    if value < 0:
                        continue
                    filtered_times.append(time_s)
                    values.append(value * scale)
                if not filtered_times:
                    continue
                max_y = max(max_y, max(values) if values else 0)
                axis.plot(filtered_times, values, linewidth=1.2, label=_label(qp_rows))
        elif source == "hires":
            for sid, pts in sorted(hires_data.items()):
                pts.sort()
                xt = [pt[0] for pt in pts]
                yt = [pt[1] for pt in pts]
                if xt:
                    max_y = max(max_y, max(yt))
                    axis.plot(xt, yt, linewidth=1.2, label=f"Sender {sid}")

        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.3)
        axis.set_xlim(min_time_s, max_time_s)
        if max_y > 0:
            axis.set_ylim(bottom=0, top=max_y * 1.1)
        else:
            axis.set_ylim(bottom=0, top=1.2) # default for utilization
            
        if schedules:
            _draw_schedule_lines(axis, schedules)

    for axis in axes:
        axis.set_xlabel("Time (s)")

    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", ncol=min(4, len(labels)))

    fig.suptitle(title)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Plot compact HPCC/HPCC+ utilization traces")
    parser.add_argument("trace_file", help="Path to utilization trace file")
    parser.add_argument("--out", required=True, help="Output PNG path")
    parser.add_argument("--config", default=None, help="Optional config file for schedule annotations")
    args = parser.parse_args()

    plot_trace(args.trace_file, args.out, args.config)


if __name__ == "__main__":
    main()