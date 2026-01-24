#!/usr/bin/env python
"""Plot cwnd-like window trace per flow.

Input format (per line):
<time_ns> <src> <dst> <sport> <dport> <rate_bps> <win_bytes>
"""
import sys
import matplotlib.pyplot as plt

def _pick_unit(max_val):
    if max_val >= 1e9:
        return "GB", 1e9
    if max_val >= 1e6:
        return "MB", 1e6
    if max_val >= 1e3:
        return "KB", 1e3
    return "B", 1


def plot_cwnd(filename):
    flows = {}
    max_win = 0
    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 7:
                continue
            try:
                t_ns = int(parts[0])
                src = int(parts[1])
                dst = int(parts[2])
                sport = int(parts[3])
                dport = int(parts[4])
                win = int(parts[6])
            except ValueError:
                continue
            key = (src, dst, sport, dport)
            if key not in flows:
                flows[key] = {"t": [], "win": []}
            flows[key]["t"].append(t_ns / 1e9)
            flows[key]["win"].append(win)
            if win > max_win:
                max_win = win

    if not flows:
        print("No data found in file")
        return

    unit, scale = _pick_unit(max_win)

    plt.figure(figsize=(12, 6))
    for (src, dst, sport, dport), data in sorted(flows.items()):
        y = [w / scale for w in data["win"]]
        label = f"{src}->{dst} ({sport}->{dport})"
        plt.plot(data["t"], y, label=label, linewidth=1.5)

    plt.xlabel("Time (s)")
    plt.ylabel(f"Window ({unit})")
    plt.title("Cwnd-like Window Over Time")
    plt.grid(True, alpha=0.3)
    if len(flows) > 1:
        plt.legend()
    plt.tight_layout()

    output_file = filename.replace(".txt", ".png")
    if output_file == filename:
        output_file = filename + ".png"
    plt.savefig(output_file, dpi=150)
    print(f"Plot saved to: {output_file}")
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        plot_cwnd(sys.argv[1])
    else:
        plot_cwnd("simulation/mix/outputs/cwnd/cwnd.txt")
