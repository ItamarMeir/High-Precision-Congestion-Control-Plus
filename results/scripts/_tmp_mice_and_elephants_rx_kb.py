from pathlib import Path
import struct
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import sys

sys.path.append(str(Path(__file__).resolve().parent))
from trace_parsers import parse_rxbuf_series


def parse_fct(path):
    rows = []
    fmt = 'IIIIQQQQ'
    sz = struct.calcsize(fmt)
    with Path(path).open('rb') as f:
        while True:
            d = f.read(sz)
            if len(d) < sz:
                break
            sip, dip, sport, dport, size, start_ns, fct_ns, _ = struct.unpack(fmt, d)
            rows.append({'size': size, 'start_s': start_ns / 1e9})
    return rows


def all_start_times(path_a, path_b):
    starts = set()
    for p in (path_a, path_b):
        for r in parse_fct(p):
            starts.add(r['start_s'])
    return sorted(starts)


def aggregate_rx_total(rx_path, t0=1.0, t1=2.0, bin_s=0.001):
    data = parse_rxbuf_series(str(rx_path))
    n_bins = int(np.ceil((t1 - t0) / bin_s))
    total = np.zeros(n_bins, dtype=float)
    for series in data.values():
        per_bin_sum = np.zeros(n_bins, dtype=float)
        per_bin_cnt = np.zeros(n_bins, dtype=int)
        for t, b in zip(series['t'], series['bytes']):
            if t < t0 or t > t1:
                continue
            idx = int((t - t0) / bin_s)
            if idx >= n_bins:
                idx = n_bins - 1
            per_bin_sum[idx] += b
            per_bin_cnt[idx] += 1
        mask = per_bin_cnt > 0
        if np.any(mask):
            per_bin_avg = np.zeros(n_bins, dtype=float)
            per_bin_avg[mask] = per_bin_sum[mask] / per_bin_cnt[mask]
            total += per_bin_avg
    x = t0 + (np.arange(n_bins) + 0.5) * bin_s
    return x, total


def find_local_maxima(x, y, min_prominence_ratio=0.03, max_points=8):
    if len(y) < 3:
        return []
    y_range = float(np.max(y) - np.min(y))
    min_prom = y_range * min_prominence_ratio
    peaks = []
    for i in range(1, len(y) - 1):
        if y[i] >= y[i - 1] and y[i] >= y[i + 1]:
            if (y[i] - min(y[i - 1], y[i + 1])) >= min_prom:
                peaks.append((x[i], y[i]))
    if not peaks:
        j = int(np.argmax(y))
        peaks = [(x[j], y[j])]
    peaks.sort(key=lambda p: p[1], reverse=True)
    return sorted(peaks[:max_points], key=lambda p: p[0])


base = Path(__file__).resolve().parents[2]

hpcc_rx   = base / 'results/study_cases/mice_and_elephants/case7_mice_and_elephants_HPCC/data/rxbuf_mice_and_elephants_HPCC.tr'
hpccp_rx  = base / 'results/study_cases/mice_and_elephants/case8_mice_and_elephants_HPCC_Plus/data/rxbuf_mice_and_elephants_HPCC_Plus.tr'
hpcc_fct  = base / 'results/study_cases/mice_and_elephants/case7_mice_and_elephants_HPCC/data/fct_mice_and_elephants_HPCC.tr'
hpccp_fct = base / 'results/study_cases/mice_and_elephants/case8_mice_and_elephants_HPCC_Plus/data/fct_mice_and_elephants_HPCC_Plus.tr'
out_png   = base / 'results/study_cases/mice_and_elephants/plots_to_show/rx_buffer_comparison_1s_to_2s_HPCC_vs_HPCC_plus.png'
title     = 'RX Buffer Comparison (1.0s-2.0s): HPCC vs HPCC+ | Mice and Elephants'

x1, y1 = aggregate_rx_total(hpcc_rx)
x2, y2 = aggregate_rx_total(hpccp_rx)
y1_kb = y1 / 1024.0
y2_kb = y2 / 1024.0
ymax  = max(np.max(y1_kb), np.max(y2_kb))

fig, ax = plt.subplots(figsize=(12.0, 5.8), dpi=170)
ax.plot(x1, y1_kb, linewidth=2.1, color='#0072B2', label='HPCC')
ax.plot(x2, y2_kb, linewidth=2.1, color='#D55E00', label='HPCC+')
ax.fill_between(x1, y1_kb, alpha=0.10, color='#0072B2')
ax.fill_between(x2, y2_kb, alpha=0.10, color='#D55E00')

FLOW_COLOR = '#5a5a5a'
flow_drawn = False
for s in all_start_times(hpcc_fct, hpccp_fct):
    if 1.0 <= s <= 2.0:
        ax.axvline(s, color=FLOW_COLOR, linestyle='--', linewidth=1.1, alpha=0.70, zorder=2)
        ax.text(s + 0.003, ymax * 0.97, f'{s:.1f}s',
                rotation=90, va='top', ha='left', fontsize=7.5, color='#3c3c3c')
        flow_drawn = True

for px, py in find_local_maxima(x1, y1_kb):
    ax.scatter([px], [py], color='#0072B2', s=22, zorder=5)
    ax.annotate(f'{py:.1f} KB', xy=(px, py), xytext=(5, 8),
                textcoords='offset points', fontsize=8, color='#004f7c')
for px, py in find_local_maxima(x2, y2_kb):
    ax.scatter([px], [py], color='#D55E00', s=22, zorder=5)
    ax.annotate(f'{py:.1f} KB', xy=(px, py), xytext=(5, -12),
                textcoords='offset points', fontsize=8, color='#8a3b00')

ax.set_xlim(1.0, 2.0)
ax.set_xlabel('Time (s)')
ax.set_ylabel('Total RX Buffer Occupancy (KB)')
ax.set_title(title)
ax.grid(True, alpha=0.25)

handles = [ax.get_lines()[0], ax.get_lines()[1]]
if flow_drawn:
    handles.append(mlines.Line2D([], [], color=FLOW_COLOR, linestyle='--',
                   linewidth=1.1, alpha=0.80, label='Flow start time'))
ax.legend(handles=handles, loc='upper right', frameon=True)
fig.tight_layout()
fig.savefig(str(out_png))
plt.close(fig)
print('Updated', out_png)
