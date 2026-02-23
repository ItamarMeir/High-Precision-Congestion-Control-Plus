# Master Plotting Script

## Overview

The `run_all_plots.py` script is a convenient way to generate all simulation analysis plots in one command.

## Usage

```bash
# From results directory
cd /workspaces/High-Precision-Congestion-Control-Plus/results

# Run all plots
python3 run_all_plots.py
```

## What It Does

The script automatically:
1. **Discovers** all available data files in `data/` directory
2. **Runs** all plot scripts with appropriate arguments
3. **Generates** visualization PNG files
4. **Reports** success/failure for each script

## Plots Generated

| Script | Output | Purpose |
|--------|--------|---------|
| `plot_qlen.py` | `qlen_*.png` | Queue length over time |
| `plot_fct.py` | `fct_*.png` | Flow completion time analysis |
| `plot_cwnd.py` | `cwnd_*.png` | Congestion window dynamics |
| `plot_queue_metrics.py` | `queue_metrics_*.png` | Queue statistics & metrics |
| `plot_dashboard.py` | `dashboard.png` | Comprehensive results overview |
| `plot_switch_throughput.py` | `switch_throughput_*.png` | Per-switch throughput analysis |

## Output

All generated plots are saved in the `data/` directory with descriptive filenames based on your data file names.

## Notes

- The script handles various argument formats automatically
- Some scripts may have specific data requirements
- Failed scripts are reported in the summary but don't halt execution
- Typical runtime: 2-5 minutes depending on data size

## Manual Running Individual Scripts

To run a specific plot script manually:

```bash
# Queue length plot
python3 scripts/plot_qlen.py data/qlen_two_senders_heavy.txt

# FCT analysis
python3 scripts/plot_fct.py data/fct_two_senders_heavy.txt

# Congestion window
python3 scripts/plot_cwnd.py data/cwnd_two_senders_heavy.txt

# Queue metrics with specific files
python3 scripts/plot_queue_metrics.py --qlen data/qlen_two_senders_heavy.txt --pfc data/pfc_two_senders_heavy.txt

# Switch throughput with trace file
python3 scripts/plot_switch_throughput.py --trace data/mix_two_senders_heavy.tr
```
