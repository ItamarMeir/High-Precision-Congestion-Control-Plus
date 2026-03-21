#!/usr/bin/env python3
"""
Ablation study comparison plot for case4_test.
Compares convergence speed at t=1.6s and t=1.8s pull-rate events across four configs:
  - baseline: all three fixes applied (MI_THRESH=1, FAST_REACT=1, C_HOST_GAIN_UP_NOQ=0.25)
  - ablation A: revert MI_THRESH=5
  - ablation B: revert FAST_REACT=0
  - ablation C: revert C_HOST_GAIN_UP_NOQ=0.0625
"""

import csv
import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))

configs = {
    "Baseline (all fixes)":           (BASE + "/data/utilization_hpcc_plus_dynamic_4.txt",       "#2ca02c", "-",  2.0),
    "Ablation A: revert MI_THRESH=5": (BASE + "/data_ablation_A/utilization_ablation_A_revert_MI_THRESH.txt",   "#1f77b4", "--", 1.5),
    "Ablation B: revert FAST_REACT=0":(BASE + "/data_ablation_B/utilization_ablation_B_revert_FAST_REACT.txt",  "#d62728", "--", 1.5),
    "Ablation C: revert GAIN=0.0625": (BASE + "/data_ablation_C/utilization_ablation_C_revert_C_HOST_GAIN_UP_NOQ.txt", "#ff7f0e", "--", 1.5),
}

LINE_RATE_GBPS = 10.0

def load_agg(fpath):
    acc = {}
    with open(fpath) as f:
        reader = csv.DictReader(f, delimiter=' ')
        for row in reader:
            try:
                t = int(row['time_ns'])
                r = float(row['r_delivered_bps'])
                acc[t] = acc.get(t, 0.0) + r
            except (KeyError, ValueError):
                pass
    return sorted(acc.items())

def bin_to_ms(agg, t_start_s, t_end_s, bin_ms=2.0):
    """Bin aggregated r_delivered into bin_ms-wide buckets, return (t_rel_ms, r_gbps) arrays."""
    t_start_ns = int(t_start_s * 1e9)
    bin_ns = int(bin_ms * 1e6)
    # Find range
    t_end_ns = int(t_end_s * 1e9)
    n_bins = int((t_end_ns - t_start_ns) / bin_ns) + 1
    bins_sum = [0.0] * n_bins
    bins_cnt = [0] * n_bins
    for t, r in agg:
        if t < t_start_ns or t >= t_end_ns:
            continue
        idx = int((t - t_start_ns) / bin_ns)
        if 0 <= idx < n_bins:
            bins_sum[idx] += r
            bins_cnt[idx] += 1
    t_ms = [i * bin_ms for i in range(n_bins)]
    r_gbps = [bins_sum[i]/bins_cnt[i]/1e9 if bins_cnt[i] > 0 else None for i in range(n_bins)]
    return t_ms, r_gbps

# Load all data
data_agg = {}
for name, (fpath, color, ls, lw) in configs.items():
    data_agg[name] = load_agg(fpath)

# Pull-rate schedule for node 2:
# t=1.0: 1.0, t=1.2: 0.05, t=1.4: 0.2, t=1.6: 0.5, t=1.8: 1.0
schedule = [
    (0.0, 0.0), (1.0, 1.0), (1.2, 0.05), (1.4, 0.2), (1.6, 0.5), (1.8, 1.0), (6.0, 1.0)
]
def pull_ceiling(t_s):
    rate = 0.0
    for ts, r in schedule:
        if t_s >= ts:
            rate = r
    return rate * LINE_RATE_GBPS

# ---- Full timeline plot ----
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

for ax_idx, (event_s, event_label, window_s, new_ceiling_gbps) in enumerate([
        (1.6, "t=1.6s event\n(pull rate 0.2->0.5, ceil=5 Gbps)", 0.32, 5.0),
        (1.8, "t=1.8s event\n(pull rate 0.5->1.0, ceil=10 Gbps)", 0.32, 10.0),
]):
    ax = axes[ax_idx]

    for name, (fpath, color, ls, lw) in configs.items():
        agg = data_agg[name]
        t_ms, r_gbps = bin_to_ms(agg, event_s - 0.02, event_s + window_s, bin_ms=1.0)
        # Offset so event fires at t=0
        t_ms_rel = [t - 20.0 for t in t_ms]

        # Filter None
        xs = [x for x, y in zip(t_ms_rel, r_gbps) if y is not None]
        ys = [y for y in r_gbps if y is not None]

        ax.plot(xs, ys, color=color, linestyle=ls, linewidth=lw, label=name)

    # Reference lines
    ax.axhline(new_ceiling_gbps * 0.90, color='gray', linestyle=':', linewidth=1.0, label=f'90% threshold ({new_ceiling_gbps*0.90:.1f} Gbps)')
    ax.axhline(new_ceiling_gbps, color='black', linestyle=':', linewidth=0.8, alpha=0.5, label=f'Ceiling ({new_ceiling_gbps:.0f} Gbps)')
    ax.axvline(0, color='black', linestyle='-', linewidth=0.8, alpha=0.4)

    ax.set_xlabel("Time relative to pull-rate event (ms)", fontsize=11)
    ax.set_ylabel("Aggregate R_delivered (Gbps)", fontsize=11)
    ax.set_title(event_label, fontsize=12, fontweight='bold')
    ax.set_xlim(-20, window_s * 1000 - 20)
    ax.set_ylim(0, new_ceiling_gbps * 1.15)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(True, alpha=0.3)

fig.suptitle("Ablation Study: Convergence Speed at Pull-Rate Events\n(case4_test, CC_MODE=11 HPCC-PLUS)",
             fontsize=13, fontweight='bold')
plt.tight_layout()

out_path = BASE + "/plots/ablation_convergence_comparison.png"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches='tight')
print(f"Saved: {out_path}")

# ---- Summary bar chart ----
fig2, axes2 = plt.subplots(1, 2, figsize=(12, 5))

def first_crossing(agg, event_s, threshold_bps, window_s=0.35):
    t_start = int(event_s * 1e9)
    t_end = int((event_s + window_s) * 1e9)
    for t, r in agg:
        if t < t_start or t > t_end:
            continue
        if r >= threshold_bps:
            return (t - t_start) / 1e6
    return window_s * 1000  # not reached within window

labels = list(configs.keys())
short_labels = ["Baseline\n(all fixes)", "Ablation A\nMI_THRESH=5", "Ablation B\nFAST_REACT=0", "Ablation C\nGAIN=0.0625"]
colors_list = [v[1] for v in configs.values()]

for ax_idx, (event_s, threshold_bps, title) in enumerate([
        (1.6, 4.5e9, "TTC@1.6s event (90% of 5 Gbps)"),
        (1.8, 9.0e9, "TTC@1.8s event (90% of 10 Gbps)"),
]):
    ax = axes2[ax_idx]
    ttcs = []
    for name in labels:
        agg = data_agg[name]
        ttc = first_crossing(agg, event_s, threshold_bps)
        ttcs.append(ttc)

    bars = ax.bar(short_labels, ttcs, color=colors_list, alpha=0.8, edgecolor='black', linewidth=0.8)

    # Annotate bars
    for bar, ttc in zip(bars, ttcs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f"{ttc:.1f} ms", ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_ylabel("Time to convergence (ms)", fontsize=11)
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, max(ttcs) * 1.3)

fig2.suptitle("Ablation Study: Time-to-Convergence Summary", fontsize=13, fontweight='bold')
plt.tight_layout()

out_path2 = BASE + "/plots/ablation_ttc_summary.png"
plt.savefig(out_path2, dpi=150, bbox_inches='tight')
print(f"Saved: {out_path2}")

plt.close('all')
print("Done.")
