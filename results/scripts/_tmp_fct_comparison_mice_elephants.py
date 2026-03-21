#!/usr/bin/env python3
"""
Generate FCT comparison tables (CSV and PNG visualization) for mice_and_elephants case.
Compares HPCC vs HPCC+ flow completion times.
"""

from pathlib import Path
import struct
import csv
import numpy as np
import matplotlib.pyplot as plt
import sys

sys.path.append(str(Path(__file__).resolve().parent))


def parse_fct_binary(path):
    """Parse binary FCT traces."""
    rows = []
    fmt = 'IIIIQQQQ'
    sz = struct.calcsize(fmt)
    with Path(path).open('rb') as f:
        while True:
            d = f.read(sz)
            if len(d) < sz:
                break
            sip, dip, sport, dport, size, start_ns, fct_ns, _ = struct.unpack(fmt, d)
            rows.append({
                'sip': hex(sip),
                'dip': hex(dip),
                'size': size,
                'start_s': start_ns / 1e9,
                'fct_ns': fct_ns,
                'fct_ms': fct_ns / 1e6
            })
    return rows


def create_fct_comparison_table(hpcc_fct_path, hpccp_fct_path, output_csv, output_png, title_suffix):
    """Create FCT comparison table (CSV and PNG visualization)."""
    
    # Parse both traces
    hpcc_rows = parse_fct_binary(hpcc_fct_path)
    hpccp_rows = parse_fct_binary(hpccp_fct_path)
    
    # Create comparison by matching flows (via start time and source)
    # Sort both by start time
    hpcc_rows.sort(key=lambda x: x['start_s'])
    hpccp_rows.sort(key=lambda x: x['start_s'])
    
    # Create CSV with comparison
    comparison_rows = []
    for i, (h, hp) in enumerate(zip(hpcc_rows, hpccp_rows)):
        delta_ms = hp['fct_ms'] - h['fct_ms']
        delta_pct = (delta_ms / h['fct_ms'] * 100) if h['fct_ms'] > 0 else 0
        
        comparison_rows.append({
            'Flow': i + 1,
            'Src': h['sip'],
            'Dst': h['dip'],
            'Size': h['size'],
            'Start_s': f"{h['start_s']:.6f}",
            'HPCC_ms': f"{h['fct_ms']:.6f}",
            'HPCC+_ms': f"{hp['fct_ms']:.6f}",
            'Delta_ms': f"{delta_ms:.6f}",
            'Delta_pct': f"{delta_pct:.3f}"
        })
    
    # Write CSV
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Flow', 'Src', 'Dst', 'Size', 'Start_s', 'HPCC_ms', 'HPCC+_ms', 'Delta_ms', 'Delta_pct'
        ])
        writer.writeheader()
        writer.writerows(comparison_rows)
    
    print(f"Saved CSV to {output_csv}")
    
    # Create visualization PNG
    # Extract numeric values for plotting
    fct_hpcc = np.array([float(row['HPCC_ms']) for row in comparison_rows])
    fct_hpccp = np.array([float(row['HPCC+_ms']) for row in comparison_rows])
    flow_ids = np.arange(1, len(comparison_rows) + 1)
    
    fig, ax = plt.subplots(figsize=(14, 6), dpi=150)
    width = 0.35
    x = np.arange(len(flow_ids))
    
    bars1 = ax.bar(x - width/2, fct_hpcc, width, label='HPCC', color='#0072B2', alpha=0.8)
    bars2 = ax.bar(x + width/2, fct_hpccp, width, label='HPCC+', color='#D55E00', alpha=0.8)
    
    ax.set_xlabel('Flow ID', fontsize=11)
    ax.set_ylabel('Flow Completion Time (ms)', fontsize=11)
    ax.set_title(f'FCT Comparison: HPCC vs HPCC+ | {title_suffix}', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(flow_ids.astype(int))
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    
    fig.tight_layout()
    fig.savefig(str(output_png), dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved PNG to {output_png}")


# Main for mice_and_elephants
base = Path(__file__).resolve().parents[2]

hpcc_fct = base / 'results/study_cases/mice_and_elephants/case7_mice_and_elephants_HPCC/data/fct_mice_and_elephants_HPCC.tr'
hpccp_fct = base / 'results/study_cases/mice_and_elephants/case8_mice_and_elephants_HPCC_Plus/data/fct_mice_and_elephants_HPCC_Plus.tr'
out_csv = base / 'results/study_cases/mice_and_elephants/plots_to_show/fct_comparison_table_HPCC_vs_HPCC_plus.csv'
out_png = base / 'results/study_cases/mice_and_elephants/plots_to_show/fct_comparison_table_HPCC_vs_HPCC_plus.png'

# Ensure output directory exists
out_csv.parent.mkdir(parents=True, exist_ok=True)

create_fct_comparison_table(hpcc_fct, hpccp_fct, out_csv, out_png, 'Mice and Elephants')
print("✓ Mice and Elephants FCT comparison completed")
