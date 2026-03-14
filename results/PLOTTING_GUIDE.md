# Master Plotting Script

## Overview

The `run_all_plots.py` script is a convenient way to generate all simulation analysis plots in one command.

## Usage

```bash
# From results directory
cd /workspaces/High-Precision-Congestion-Control-Plus/results

# Run all plots (uses local data/ and plots/ directories by default)
python3 run_all_plots.py

# Run for a specific study case or alternative directory
python3 run_all_plots.py --base-dir study_cases/case4_large_rx_buffer_HPCC
```

## What It Does

The script automatically:
1. **Discovers** all available data files in `data/` directory
2. **Runs** all plot scripts with appropriate arguments
3. **Generates** visualization PNG files
4. **Reports** success/failure for each script

## Plots Generated

The master script generates both static PNGs (in `plots/`) and interactive HTML dashboards (in `interactive_plots/`).

### Static Plots (`plots/`)

| Script | Output Pattern | Purpose |
|--------|----------------|---------|
| `plot_topology.py` | `topology_analysis.png` | Network Topology Visualization (Full + Flows) |
| `plot_fct.py` | `fct_[exp].png` | Flow Completion Time Analysis |
| `plot_rx_buffer.py` | `rx_buffer_[exp].png` | Receiver (NIC) Buffer Occupancy |
| `plot_packet_drops.py` | `reliability_analysis_[exp].png` | Packet Drop and PFC Pause Analysis |
| `plot_queue_metrics.py` | *Queue plots (e.g., CDFs)* | Queue statistics & metrics including PFC |
| `plot_utilization_metrics.py` | `utilization_[exp].png` | Switch vs Host Utilization Metrics |
| `plot_ack_analysis.py` | `ack_analysis_[exp].png` | ACK Analysis Dashboard |
| `plot_cwnd_rtt_analysis.py` | `cwnd_rate_analysis_[exp].png` | CWND & Rate Analysis Dashboard |
| `plot_switch_throughput.py` | `switch_throughput_[exp].png` | Per-switch Throughput Analysis |
| `plot_dashboard.py` | `dashboard_[exp].png` | Comprehensive Static Overview |

### Interactive Plots (`interactive_plots/`)

| Script | Output Pattern | Purpose |
|--------|----------------|---------|
| `plot_interactive_dashboard.py`| *Multiple `.html` files* | Full Interactive Exploratory Dashboards |
| `plot_utilization_metrics_interactive.py` | `utilization_[exp].html` | Interactive Utilization Metrics |
| `plot_ack_analysis_interactive.py` | `ack_analysis_[exp].html` | Interactive ACK Analysis |

## Output

Generated static plots are saved in the `plots/` directory, while interactive HTML files are saved to `interactive_plots/`. Filenames are descriptive and include the specific simulation tag.

## Notes

- The script handles various argument formats and config finding automatically
- Some scripts may have specific data requirements (e.g., traces)
- Failed scripts are reported in the summary but don't halt execution
- Typical runtime: 2-5 minutes depending on data size

## Manual Running Individual Scripts

To run a specific plot script manually:

```bash
# RX buffer occupancy
python3 scripts/plot_rx_buffer.py data/rxbuf_my_exp.txt

# FCT analysis
python3 scripts/plot_fct.py data/fct_my_exp.txt

# Congestion window and Rate
python3 scripts/plot_cwnd_rtt_analysis.py data/cwnd_my_exp.txt config_my_exp.txt

# Switch throughput with trace file
python3 scripts/plot_switch_throughput.py --trace data/mix_my_exp.tr --config config_my_exp.txt

# Interactive Utilization
python3 scripts/plot_utilization_metrics_interactive.py data/utilization_my_exp.txt interactive_plots/utilization_my_exp.html config_my_exp.txt
```
