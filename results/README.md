# HPCC Simulation Results

This folder contains organized visualization scripts, plots, and raw data from HPCC (High Precision Congestion Control) simulator runs.

## Directory Structure

```
results/
├── README.md              # This file
├── scripts/               # Visualization scripts
│   ├── plot_qlen.py      # Queue length time-series visualization
│   ├── plot_fct.py       # Flow completion time analysis
│   └── plot_dashboard.py # Comprehensive results dashboard
├── plots/                # Generated visualization images
│   ├── dashboard.png     # Full results dashboard
│   ├── fct.png          # FCT analysis charts
│   └── qlen.png         # Queue length time-series
└── data/                # Raw simulation output data
    ├── fct.txt          # Flow completion time records
    └── qlen.txt         # Queue length samples
```

## Usage

### Quick View
Simply open the PNG files in your image viewer:
- **[plots/dashboard.png](plots/dashboard.png)** - Most comprehensive overview
- **[plots/fct.png](plots/fct.png)** - Detailed FCT analysis
- **[plots/qlen.png](plots/qlen.png)** - Queue dynamics

### Regenerate Visualizations

After running new simulations, regenerate plots:

```bash
# From results directory
cd /workspaces/High-Precision-Congestion-Control-Plus

# Option 1: Generate specific plot
python3 results/scripts/plot_qlen.py simulation/mix/qlen.txt

# Option 2: Generate FCT analysis
python3 results/scripts/plot_fct.py simulation/mix/fct.txt

# Option 3: Generate full dashboard
python3 results/scripts/plot_dashboard.py simulation/mix
```

Then copy updated files to results folder:
```bash
cp simulation/mix/*.png results/plots/
cp simulation/mix/{fct,qlen}.txt results/data/
```

## Data Format

### fct.txt (Flow Completion Time)
Format: `src_ip dst_ip sport dport base_fct start_time fct flow_size`

Example:
```
0b000301 0b000101 10000 100 200000000 2000000000 35669855 16772160
```

Fields:
- `src_ip`: Source IP address (hex)
- `dst_ip`: Destination IP address (hex)
- `sport`: Source port
- `dport`: Destination port
- `base_fct`: Ideal FCT in nanoseconds (based on flow size and link rate)
- `start_time`: Flow start time in nanoseconds
- `fct`: Actual flow completion time in nanoseconds
- `flow_size`: Flow size in bytes

### qlen.txt (Queue Length)
Format: `timestamp queue_length`

Example:
```
2000000000 0
2000003000 4000
```

Fields:
- `timestamp`: Time in nanoseconds
- `queue_length`: Queue length in bytes

## Visualization Scripts

### plot_dashboard.py
Comprehensive dashboard showing:
- Configuration parameters
- Queue length timeline
- FCT vs flow size scatter plot
- Slowdown analysis
- Flow execution timeline
- Statistical summaries
- Distribution histograms

**Usage:**
```bash
python3 scripts/plot_dashboard.py [data_directory]
```

### plot_fct.py
Detailed FCT analysis with:
- FCT vs flow size (log-log plot)
- Slowdown vs flow size
- FCT distribution histogram
- Statistical summary

**Usage:**
```bash
python3 scripts/plot_fct.py simulation/mix/fct.txt
```

### plot_qlen.py
Simple queue length visualization:
- Time-series plot of queue length
- Shows congestion patterns

**Usage:**
```bash
python3 scripts/plot_qlen.py simulation/mix/qlen.txt
```

## Key Metrics Explained

### Flow Completion Time (FCT)
Time from when a flow starts until all its data is delivered.

### Slowdown
Ratio of actual FCT to ideal FCT (ideal = flow_size / link_bandwidth)
- Slowdown = 1.0: Perfect, no congestion impact
- Slowdown > 1.0: Flow delayed by congestion

### Ideal FCT (Base FCT)
Theoretical minimum FCT if the flow had dedicated link capacity:
```
base_fct = flow_size / bandwidth
```

## Dependencies

The visualization scripts require:
- Python 3
- matplotlib
- numpy

Install via:
```bash
apt-get install python3-matplotlib python3-numpy
```

## Tips for Interpretation

1. **Queue Length Plot**
   - Flat line at 0: No congestion
   - Peaks indicate congestion events
   - Sharp drops show packet drains

2. **FCT Analysis**
   - Flows should cluster near slowdown = 1.0
   - Large flows typically show higher slowdown
   - HPCC aims to keep slowdown < 2.0

3. **Dashboard**
   - Use for quick performance overview
   - Compare across different CC schemes
   - Identify outliers and anomalies

## Example Workflow

```bash
# 1. Run simulation
cd simulation
./waf --run 'scratch/third mix/config.txt'

# 2. Generate plots
cd ..
python3 plot_dashboard.py

# 3. Copy to results
cp simulation/mix/*.png results/plots/
cp simulation/mix/{fct,qlen}.txt results/data/

# 4. View results
open results/plots/dashboard.png
```

## Notes

- Plots are generated at 150 DPI for screen and print use
- All timestamps are in nanoseconds in raw data
- Visualizations automatically convert to appropriate units (seconds for time, ms for FCT)
- Multiple runs should have timestamped subdirectories for organization

## Further Analysis

For more advanced analysis, see:
- `analysis/fct_analysis.py` - Statistical FCT analysis across multiple runs
- `analysis/trace_reader` - Detailed packet-level trace parsing
- Documentation in `analysis/README.md`
