#!/usr/bin/env python3
"""Generate FCT comparison CSV and table PNG for elephants_rx_buffer."""

from pathlib import Path
import struct
import csv
import matplotlib.pyplot as plt


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
                'sport': sport,
                'dport': dport,
                'size': size,
                'start_s': start_ns / 1e9,
                'end_s': (start_ns + fct_ns) / 1e9,
                'fct_ms': fct_ns / 1e6,
            })
    return rows


def _delta_cell_color(delta_pct, max_abs_pct):
    """Green when HPCC+ is better (delta > 0), red when HPCC is better (delta < 0)."""
    if max_abs_pct <= 0:
        return (1.0, 1.0, 1.0)
    intensity = min(1.0, abs(delta_pct) / max_abs_pct)
    if delta_pct > 0:
        return (0.90 - 0.35 * intensity, 1.0, 0.90 - 0.35 * intensity)
    if delta_pct < 0:
        return (1.0, 0.90 - 0.35 * intensity, 0.90 - 0.35 * intensity)
    return (1.0, 1.0, 1.0)


def create_fct_comparison_table(hpcc_fct_path, hpccp_fct_path, output_csv, output_png, title):
    hpcc_rows = parse_fct_binary(hpcc_fct_path)
    hpccp_rows = parse_fct_binary(hpccp_fct_path)

    hpcc_rows.sort(key=lambda x: (x['sip'], x['dip'], x['size'], x['start_s']))
    hpccp_rows.sort(key=lambda x: (x['sip'], x['dip'], x['size'], x['start_s']))

    n = min(len(hpcc_rows), len(hpccp_rows))
    rows = []
    for i in range(n):
        h = hpcc_rows[i]
        hp = hpccp_rows[i]
        delta_ms = h['fct_ms'] - hp['fct_ms']
        rows.append({
            'Flow': i + 1,
            'Start_s': h['start_s'],
            'End_HPCC_s': h['end_s'],
            'End_HPCC+_s': hp['end_s'],
            'HPCC_FCT_ms': h['fct_ms'],
            'HPCC+_FCT_ms': hp['fct_ms'],
            'Delta_FCT_ms': delta_ms,
            'Delta_pct': (delta_ms / h['fct_ms'] * 100.0) if h['fct_ms'] > 0 else 0.0,
        })

    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'Flow',
                'Start_s',
                'End_HPCC_s',
                'End_HPCC+_s',
                'HPCC_FCT_ms',
                'HPCC+_FCT_ms',
                'Delta_FCT_ms',
                'Delta_pct',
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({
                'Flow': r['Flow'],
                'Start_s': f"{r['Start_s']:.6f}",
                'End_HPCC_s': f"{r['End_HPCC_s']:.6f}",
                'End_HPCC+_s': f"{r['End_HPCC+_s']:.6f}",
                'HPCC_FCT_ms': f"{r['HPCC_FCT_ms']:.6f}",
                'HPCC+_FCT_ms': f"{r['HPCC+_FCT_ms']:.6f}",
                'Delta_FCT_ms': f"{r['Delta_FCT_ms']:.6f}",
                'Delta_pct': f"{r['Delta_pct']:.3f}",
            })

    headers = [
        'Flow',
        'Start (s)',
        'End HPCC (s)',
        'End HPCC+ (s)',
        'HPCC FCT (ms)',
        'HPCC+ FCT (ms)',
        'Delta (HPCC-HPCC+) ms',
        'Delta %',
    ]
    table_data = [
        [
            str(r['Flow']),
            f"{r['Start_s']:.6f}",
            f"{r['End_HPCC_s']:.6f}",
            f"{r['End_HPCC+_s']:.6f}",
            f"{r['HPCC_FCT_ms']:.6f}",
            f"{r['HPCC+_FCT_ms']:.6f}",
            f"{r['Delta_FCT_ms']:.6f}",
            f"{r['Delta_pct']:.3f}",
        ]
        for r in rows
    ]

    max_abs_pct = max((abs(r['Delta_pct']) for r in rows), default=0.0)

    fig_h = max(3.2, 1.2 + 0.42 * (len(table_data) + 1))
    fig, ax = plt.subplots(figsize=(16, fig_h), dpi=170)
    ax.axis('off')
    ax.set_title(
        f"{title}\nGreen = HPCC+ better, Red = HPCC better",
        fontsize=12,
        fontweight='bold',
        pad=16,
    )

    tbl = ax.table(cellText=table_data, colLabels=headers, loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1.0, 1.3)

    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor('#666666')
        if r == 0:
            cell.set_facecolor('#efefef')
            cell.set_text_props(weight='bold')
        elif c in (6, 7):
            delta_pct_val = rows[r - 1]['Delta_pct']
            cell.set_facecolor(_delta_cell_color(delta_pct_val, max_abs_pct))

    fig.tight_layout()
    fig.savefig(str(output_png), bbox_inches='tight')
    plt.close(fig)

    print(f"Saved CSV to {output_csv}")
    print(f"Saved table PNG to {output_png}")


base = Path(__file__).resolve().parents[2]

hpcc_fct = base / 'results/study_cases/elephants_rx_buffer/case9_elephants_rx_buffer_HPPC/data/fct_elephants_rx_buffer_HPPC.tr'
hpccp_fct = base / 'results/study_cases/elephants_rx_buffer/case10_elephants_rx_buffer_HPPC_Plus/data/fct_elephants_rx_buffer_HPPC_Plus.tr'
out_csv = base / 'results/study_cases/elephants_rx_buffer/plots_to_show/fct_comparison_table_HPCC_vs_HPCC_plus.csv'
out_png = base / 'results/study_cases/elephants_rx_buffer/plots_to_show/fct_comparison_table_HPCC_vs_HPCC_plus.png'
out_csv.parent.mkdir(parents=True, exist_ok=True)

create_fct_comparison_table(
    hpcc_fct,
    hpccp_fct,
    out_csv,
    out_png,
    'FCT Comparison Table: HPCC vs HPCC+ | Elephants RX Buffer',
)
print('✓ Elephants RX Buffer FCT table completed')
